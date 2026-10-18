import html
import json
import logging
import os
import re
import unicodedata
from copy import copy
from pathlib import Path
from string import Template
from threading import Lock
from typing import cast
import requests

from scholar_translator.cache import TranslationCache
from scholar_translator.config import ConfigManager

from tenacity import retry, retry_if_not_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential


logger = logging.getLogger(__name__)


def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0] != "C")


class BaseTranslator:
    name = "base"
    envs = {}
    lang_map: dict[str, str] = {}
    CustomPrompt = False

    def __init__(self, lang_in: str, lang_out: str, model: str, ignore_cache: bool):
        lang_in = self.lang_map.get(lang_in.lower(), lang_in)
        lang_out = self.lang_map.get(lang_out.lower(), lang_out)
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.model = model
        self.ignore_cache = ignore_cache

        self.cache = TranslationCache(
            self.name,
            {
                "lang_in": lang_in,
                "lang_out": lang_out,
                "model": model,
            },
        )

    def set_envs(self, envs):
        # Detach from self.__class__.envs
        # Cannot use self.envs = copy(self.__class__.envs)
        # because if set_envs called twice, the second call will override the first call
        self.envs = copy(self.envs)
        if ConfigManager.get_translator_by_name(self.name):
            self.envs = ConfigManager.get_translator_by_name(self.name)
        needUpdate = False
        for key in self.envs:
            if key in os.environ:
                self.envs[key] = os.environ[key]
                needUpdate = True
        if needUpdate:
            ConfigManager.set_translator_by_name(self.name, self.envs)
        if envs is not None:
            for key in envs:
                self.envs[key] = envs[key]
            ConfigManager.set_translator_by_name(self.name, self.envs)

    def add_cache_impact_parameters(self, k: str, v):
        """
        Add parameters that affect the translation quality to distinguish the translation effects under different parameters.
        :param k: key
        :param v: value
        """
        self.cache.add_params(k, v)

    def translate(self, text: str, ignore_cache: bool = False, **kwargs) -> str:
        """
        Translate the text, and the other part should call this method.
        :param text: text to translate
        :param ignore_cache: whether to ignore cache
        :param kwargs: additional parameters (e.g., rate_limit_params for babeldoc compatibility)
        :return: translated text
        """
        if not (self.ignore_cache or ignore_cache):
            cache = self.cache.get(text)
            if cache is not None:
                validated = self.validate_cached_translation(text, cache)
                if validated is not None:
                    return validated

        translation = self.do_translate(text)
        self.cache.set(text, translation)
        return translation

    def validate_cached_translation(self, source: str, translation: str) -> str | None:
        return translation

    def do_translate(self, text: str) -> str:
        """
        Actual translate text, override this method
        :param text: text to translate
        :return: translated text
        """
        raise NotImplementedError

    def prompt(
        self, text: str, prompt_template: Template | None = None
    ) -> list[dict[str, str]]:
        try:
            return [
                {
                    "role": "user",
                    "content": cast(Template, prompt_template).safe_substitute(
                        {
                            "lang_in": self.lang_in,
                            "lang_out": self.lang_out,
                            "text": text,
                        }
                    ),
                }
            ]
        except AttributeError:  # `prompt_template` is None
            pass
        except Exception:
            logging.exception("Error parsing prompt, use the default prompt.")

        return [
            {
                "role": "user",
                "content": (
                    "You are a professional, authentic machine translation engine. "
                    "Only Output the translated text, do not include any other text."
                    "\n\n"
                    f"Translate the following markdown source text to {self.lang_out}. "
                    "Keep the formula notation {v*} unchanged. "
                    "Output translation directly without any additional text."
                    "\n\n"
                    f"Source Text: {text}"
                    "\n\n"
                    "Translated Text:"
                ),
            },
        ]

    def __str__(self):
        return f"{self.name} {self.lang_in} {self.lang_out} {self.model}"

    def get_rich_text_left_placeholder(self, id: int):
        return f"<b{id}>"

    def get_rich_text_right_placeholder(self, id: int):
        return f"</b{id}>"

    def get_formular_placeholder(self, id: int):
        return self.get_rich_text_left_placeholder(
            id
        ) + self.get_rich_text_right_placeholder(id)


class GeminiTranslator(BaseTranslator):
    name = "gemini"
    lang_map = {"ko": "ko"}

    def __init__(self, lang_in, lang_out, model, ignore_cache=False, **kwargs):
        from scholar_translator.gemini_client import (
            GeminiClient, DEFAULT_MODEL, PROMPT_VERSION, api_key_from_environment,
        )
        chosen_model = model or os.environ.get("QDT_GEMINI_MODEL") or DEFAULT_MODEL
        super().__init__(lang_in, lang_out, chosen_model, ignore_cache)
        self.cache.add_params("prompt_version", PROMPT_VERSION)
        self.client = GeminiClient(api_key_from_environment(), chosen_model)

    def validate_cached_translation(self, source, translation):
        return self.client.validate_cached_translation(source, translation)

    def do_translate(self, text):
        return self.client.translate(text, self.lang_out)


class GoogleTranslator(BaseTranslator):
    name = "google"
    lang_map = {"ko": "ko"}

    def __init__(self, lang_in, lang_out, model, ignore_cache=False, **kwargs):
        super().__init__(lang_in, lang_out, model, ignore_cache)
        self.session = requests.Session()
        self.endpoint = "https://translate.google.com/m"
        self.headers = {
            "User-Agent": "Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)"  # noqa: E501
        }

    def do_translate(self, text):
        text = text[:5000]  # google translate max length
        response = self.session.get(
            self.endpoint,
            params={"tl": self.lang_out, "sl": self.lang_in, "q": text},
            headers=self.headers,
            timeout=(5, 30),
        )
        if response.status_code == 429:
            from scholar_translator.gemini_client import GeminiError
            raise GeminiError("QDT_GOOGLE_RATE_LIMITED", "Google 웹 번역 요청 제한입니다. 기다린 뒤 다시 시도하거나 설정한 API 엔진을 직접 선택하세요.")
        re_result = re.findall(
            r'(?s)class="(?:t0|result-container)">(.*?)<', response.text
        )
        if response.status_code == 400:
            result = "IRREPARABLE TRANSLATION ERROR"
        else:
            response.raise_for_status()
            result = html.unescape(re_result[0])
        return remove_control_characters(result)


class OfflineTranslator(BaseTranslator):
    name = "offline"
    envs = {
        "OFFLINE_TRANSLATION_MAP": None,
        "OFFLINE_TASK_OUTPUT": None,
    }

    def __init__(
        self,
        lang_in,
        lang_out,
        model,
        envs=None,
        prompt=None,
        ignore_cache=False,
        **kwargs,
    ):
        self.envs = copy(self.__class__.envs)
        for key in self.envs:
            if key in os.environ:
                self.envs[key] = os.environ[key]
        if envs is not None:
            for key in envs:
                self.envs[key] = envs[key]

        self.translation_map_path = self.envs.get("OFFLINE_TRANSLATION_MAP")
        self.task_output_path = self.envs.get("OFFLINE_TASK_OUTPUT")
        self.extracting_tasks = bool(self.task_output_path and not self.translation_map_path)
        self.translations: dict[str, str] = {}
        self._seen_tasks: dict[str, int] = {}
        self._task_lock = Lock()

        # When an offline translation map is present it IS the authoritative
        # source of truth (the agent already translated every task). Bypass the
        # persistent sqlite translation cache: its key is keyed on the map PATH,
        # not its contents, so a stale value from an earlier run on the same path
        # (e.g. an untranslated English header from before extraction was fixed)
        # would shadow the map and render the original text. extracting_tasks
        # already ignores cache; do the same whenever a map drives the render.
        bypass_cache = ignore_cache or self.extracting_tasks or bool(self.translation_map_path)
        super().__init__(lang_in, lang_out, model, bypass_cache)
        self.add_cache_impact_parameters("offline_map", self.translation_map_path)
        self.add_cache_impact_parameters("task_output", self.task_output_path)

        if self.translation_map_path:
            self.translations = self._load_translation_map(self.translation_map_path)
        elif self.task_output_path:
            self._prepare_task_output(self.task_output_path)
        else:
            raise ValueError(
                "Offline translation requires OFFLINE_TRANSLATION_MAP or "
                "OFFLINE_TASK_OUTPUT."
            )

    def _load_translation_map(self, map_path: str) -> dict[str, str]:
        path = Path(map_path)
        if not path.exists():
            raise ValueError(f"Offline translation map not found: {path}")

        translations: dict[str, str] = {}
        with path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in offline translation map at line {line_number}: {exc}"
                    ) from exc

                source = row.get("source")
                translation = row.get("translation")
                if not isinstance(source, str) or not isinstance(translation, str):
                    raise ValueError(
                        "Offline translation map rows require string "
                        f"'source' and 'translation' fields at line {line_number}."
                    )

                existing = translations.get(source)
                if existing is not None and existing != translation:
                    raise ValueError(
                        "Conflicting offline translations for source at "
                        f"line {line_number}: {source[:80]}"
                    )
                translations[source] = translation
        return translations

    def do_translate(self, text):
        if self.extracting_tasks:
            self._write_task(text)
            return text

        if self.translations:
            translated = self.translations.get(text)
            if translated is None:
                # The offline map is built from an LLM batch pass, which may not
                # echo every render-time source byte-for-byte (formula markers,
                # whitespace, reference-state differences). A miss here is a
                # PERMANENT failure: raising propagates into converter.py's
                # unbounded `@retry(wait=wait_fixed(1))` worker and hangs the
                # whole render forever. Fall back to the source text so the
                # render still completes, and log the gap for visibility.
                logging.warning(
                    "Offline translation map missing source; leaving untranslated: %s",
                    text[:120],
                )
                return text
            return remove_control_characters(translated)

        return text

    # Paths whose task file has already been truncated in this process. A single
    # extraction run constructs multiple OfflineTranslator instances (per page /
    # converter), so truncating on every construction would wipe the tasks
    # written by earlier instances and only the last batch would survive.
    _prepared_task_paths: set[str] = set()

    def _prepare_task_output(self, task_output_path: str) -> None:
        path = Path(task_output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        resolved = str(path.resolve())
        if resolved not in OfflineTranslator._prepared_task_paths:
            # Start clean once per run, then accumulate across instances.
            path.write_text("", encoding="utf-8")
            OfflineTranslator._prepared_task_paths.add(resolved)
        elif path.exists():
            # Preload already-recorded sources so dedup stays global across the
            # multiple translator instances writing to the same task file.
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    source = json.loads(line).get("source")
                except json.JSONDecodeError:
                    continue
                if isinstance(source, str) and source not in self._seen_tasks:
                    self._seen_tasks[source] = len(self._seen_tasks) + 1

    def _write_task(self, text: str) -> None:
        with self._task_lock:
            if text in self._seen_tasks:
                return

            self._seen_tasks[text] = len(self._seen_tasks) + 1
            path = Path(self.task_output_path)
            with path.open("a", encoding="utf-8") as file:
                file.write(
                    json.dumps(
                        {"id": self._seen_tasks[text], "source": text},
                        ensure_ascii=False,
                    )
                    + "\n"
                )


class BedrockTranslator(BaseTranslator):
    # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime.html
    name = "bedrock"
    CustomPrompt = True

    # Model shortcuts mapping for convenience
    MODEL_MAP = {
        "claude-4.5-opus": "global.anthropic.claude-opus-4-5-20251101-v1:0",
        "claude-4.5-sonnet": "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "claude-4.5-haiku": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    }

    envs = {
        "AWS_REGION": "us-west-2",
        "AWS_ACCESS_KEY_ID": None,
        "AWS_SECRET_ACCESS_KEY": None,
        "AWS_SESSION_TOKEN": None,
        "BEDROCK_MODEL_ID": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    }

    def __init__(
        self,
        lang_in,
        lang_out,
        model,
        envs=None,
        prompt=None,
        ignore_cache=False,
        **kwargs,
    ):
        # Check if boto3 is installed
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError:
            raise ImportError(
                "boto3 is not installed. Install with: pip install scholar-translator[bedrock]"
            )

        self.set_envs(envs)

        # Resolve model shortcut to full Bedrock model ID
        if not model:
            model = self.envs["BEDROCK_MODEL_ID"]
        model = self.MODEL_MAP.get(model, model)

        super().__init__(lang_in, lang_out, model, ignore_cache)

        self.options = {
            "temperature": 0,
            "max_tokens": 2000,
        }
        self.prompttext = prompt

        # Initialize Bedrock client with authentication
        # Priority: IAM role (default) -> explicit credentials
        aws_region = self.envs.get("AWS_REGION") or "us-west-2"
        if not aws_region or aws_region.strip() == "":
            aws_region = "us-west-2"
        client_kwargs = {"region_name": aws_region}

        if self.envs["AWS_ACCESS_KEY_ID"] and self.envs["AWS_SECRET_ACCESS_KEY"]:
            client_kwargs["aws_access_key_id"] = self.envs["AWS_ACCESS_KEY_ID"]
            client_kwargs["aws_secret_access_key"] = self.envs["AWS_SECRET_ACCESS_KEY"]
            if self.envs["AWS_SESSION_TOKEN"]:
                client_kwargs["aws_session_token"] = self.envs["AWS_SESSION_TOKEN"]

        try:
            self.client = boto3.client("bedrock-runtime", **client_kwargs)
        except Exception as e:
            raise ValueError(
                f"Failed to initialize AWS Bedrock client: {e}\n"
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, "
                "or configure IAM role if running on AWS."
            )

        # Add cache impact parameters
        self.add_cache_impact_parameters("temperature", self.options["temperature"])
        self.add_cache_impact_parameters("max_tokens", self.options["max_tokens"])
        self.add_cache_impact_parameters("prompt", self.prompt("", self.prompttext))

        # Store ClientError for retry logic
        self.ClientError = ClientError

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_not_exception_type(ValueError),
        before_sleep=lambda retry_state: logger.warning(
            f"Bedrock rate limit or error, retrying in {retry_state.next_action.sleep} seconds... "
            f"(Attempt {retry_state.attempt_number}/5)"
        ),
    )
    def do_translate(self, text) -> str:
        import json
        from botocore.exceptions import ClientError

        # Construct Messages API format for Claude models
        messages = self.prompt(text, self.prompttext)

        # Convert to Bedrock format
        bedrock_messages = []
        for msg in messages:
            bedrock_messages.append({"role": msg["role"], "content": msg["content"]})

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.options["max_tokens"],
            "temperature": self.options["temperature"],
            "messages": bedrock_messages,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model, body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"].strip()
            return content

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            # Don't retry on validation or access errors
            if error_code in ["ValidationException", "AccessDeniedException"]:
                raise ValueError(
                    f"AWS Bedrock error ({error_code}): {e.response['Error']['Message']}"
                )

            # Retry on throttling and service errors
            if error_code in [
                "ThrottlingException",
                "ServiceUnavailableException",
                "TooManyRequestsException",
            ]:
                raise  # Will be caught by retry decorator

            # Unknown error, log and raise
            logger.error(f"Unexpected Bedrock error: {error_code} - {e}")
            raise


class CodexCliTranslator(BaseTranslator):
    """Translation backend using Codex CLI."""

    name = "codex-cli"

    def __init__(self, lang_in, lang_out, model=None, envs=None, prompt=None, ignore_cache=False, **kwargs):
        super().__init__(lang_in, lang_out, model or "codex", ignore_cache)

        # Import and initialize the CLI adapter
        try:
            from qdt_agents.codex_cli import CodexCliEngine
            self.engine = CodexCliEngine(cli_path=kwargs.get("cli_path", "codex"))
        except ImportError:
            raise ImportError("agent-adapters package not installed. Run: pip install -e services/agent-adapters")

    def do_translate(self, text: str) -> str:
        """Translate text using Codex CLI."""
        return self.engine.translate(
            text=text,
            source_lang=self.lang_in,
            target_lang=self.lang_out,
        )


class ClaudeCodeCliTranslator(BaseTranslator):
    """Translation backend using Claude Code CLI."""

    name = "claude-code-cli"

    def __init__(self, lang_in, lang_out, model=None, envs=None, prompt=None, ignore_cache=False, **kwargs):
        super().__init__(lang_in, lang_out, model or "claude", ignore_cache)

        # Import and initialize the CLI adapter
        try:
            from qdt_agents.claude_code_cli import ClaudeCodeCliEngine
            self.engine = ClaudeCodeCliEngine(cli_path=kwargs.get("cli_path", "claude"))
        except ImportError:
            raise ImportError("agent-adapters package not installed. Run: pip install -e services/agent-adapters")

    def do_translate(self, text: str) -> str:
        """Translate text using Claude Code CLI."""
        return self.engine.translate(
            text=text,
            source_lang=self.lang_in,
            target_lang=self.lang_out,
        )
