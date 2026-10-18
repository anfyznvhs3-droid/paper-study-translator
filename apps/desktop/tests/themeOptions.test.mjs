import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";
import vm from "node:vm";
import ts from "typescript";

function loadThemeOptions() {
  const source = fs.readFileSync(new URL("../src/theme/themeOptions.ts", import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020
    }
  });
  const context = { exports: {} };
  vm.runInNewContext(outputText, context);
  return context.exports;
}

test("soft pink preset keeps the selected C1 gradient", () => {
  const { getThemeTokens } = loadThemeOptions();

  const tokens = getThemeTokens("soft-pink");

  assert.equal(tokens.gradientStart, "#ffd6ec");
  assert.equal(tokens.gradientEnd, "#e8c7ff");
  assert.equal(tokens.primary, "#ff8acb");
  assert.equal(tokens.accent, "#b992ff");
});

test("theme tokens convert to app css variables", () => {
  const { getThemeTokens, themeCssVariables } = loadThemeOptions();

  const variables = themeCssVariables(getThemeTokens("soft-pink"));

  assert.equal(variables["--bg"], "#fbf7fc");
  assert.equal(variables["--blue"], "#ff8acb");
  assert.equal(variables["--green"], "#b992ff");
  assert.match(variables["--primary-gradient"], /#ffd6ec/);
  assert.match(variables["--primary-gradient"], /#e8c7ff/);
});

test("custom preset returns the supplied theme tokens", () => {
  const { defaultCustomTheme, getThemeTokens } = loadThemeOptions();
  const custom = { ...defaultCustomTheme, primary: "#ff66aa" };

  assert.equal(getThemeTokens("custom", custom).primary, "#ff66aa");
});

test("dark mode swaps a preset to its dark-friendly palette", () => {
  const { getThemeTokens } = loadThemeOptions();

  const light = getThemeTokens("soft-pink", undefined, false);
  const dark = getThemeTokens("soft-pink", undefined, true);

  // Background goes dark, text goes light, but it stays a pink theme.
  assert.notEqual(dark.background, light.background);
  assert.match(dark.primary, /^#ff/i);
  assert.equal(dark.text, "#f5e7f1");
});

test("dark mode keeps the user's brand colors on a dark base for custom", () => {
  const { defaultCustomTheme, getThemeTokens } = loadThemeOptions();
  const custom = { ...defaultCustomTheme, primary: "#ff66aa", accent: "#66ccff" };

  const dark = getThemeTokens("custom", custom, true);

  assert.equal(dark.primary, "#ff66aa"); // brand preserved
  assert.equal(dark.accent, "#66ccff");
  assert.notEqual(dark.background, custom.background); // base goes dark
  assert.equal(dark.gradientStart, "#ff66aa");
});

test("primary actions retain the existing gradient and readable text across its entire fill", () => {
  const { themePresets, themePresetsDark, defaultCustomTheme, themeCssVariables, colorChannels, contrastRatio } = loadThemeOptions();
  const soft = themeCssVariables(themePresets["soft-pink"]);
  assert.equal(soft["--action-start"], "#ffd6ec");
  assert.equal(soft["--action-end"], "#e8c7ff");
  for (const tokens of [...Object.values(themePresets), ...Object.values(themePresetsDark),
    { ...defaultCustomTheme, gradientStart: "#000000", gradientEnd: "#ffffff" }]) {
    const vars = themeCssVariables(tokens);
    const a = colorChannels(vars["--action-start"]), b = colorChannels(vars["--action-end"]);
    for (let i = 0; i <= 20; i++) {
      const fill = `rgb(${a.map((value, k) => Math.round((value + (b[k] - value) * i / 20) * 255)).join(",")})`;
      assert.ok(contrastRatio(fill, vars["--action-fg"]) >= 4.5, fill);
    }
  }
});
