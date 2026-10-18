"""Reproduce the public README examples using recorded Codex translations.

Downloads only the attributed public inputs. After downloading, blocks network
connections and runs the application's unmodified PDF/OCR pipeline. No API key
or private profile is read. See ATTRIBUTION.md and ../SHOWCASE.md.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import socket
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PAPER_URL = 'https://aclanthology.org/2025.emnlp-demos.71.pdf'
DATA_URL = ('https://raw.githubusercontent.com/allisonhorst/palmerpenguins/'
            '8957207b78d6ccd1b4654a9dd9c9041b657478ab/inst/extdata/penguins.csv')
INPUTS = {
    'paper.pdf': (PAPER_URL, 'ee11e6a2301cd980d4d7663d2ed8e4f85df414fe1ea775bc5fbb8cf660c6b187'),
    'penguins.csv': (DATA_URL, 'f204db2c753b0937caac3cb35258562c14f073e4bbc76be24b4c51ce22767a93'),
}


def fetch(work):
    for name, (url, digest) in INPUTS.items():
        path = work / name
        if not path.exists():
            with urllib.request.urlopen(url, timeout=60) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError(f'Public input changed: {name}')
            path.write_bytes(data)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Unexpected input: {name}')


def chart(work):
    import fitz
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    with (work / 'penguins.csv').open(encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    complete = [r for r in rows if r['bill_length_mm'] != 'NA' and r['flipper_length_mm'] != 'NA']
    assert (len(rows), len(complete)) == (344, 342)
    fig, ax = plt.subplots(figsize=(9, 6.5), dpi=180)
    fig.subplots_adjust(left=.11, right=.96, bottom=.15, top=.71)
    fig.patch.set_facecolor('white')
    for species, color, marker in [('Adelie', '#9274c8', 'o'), ('Chinstrap', '#d8799d', '^'), ('Gentoo', '#538e9f', 's')]:
        group = [r for r in complete if r['species'] == species]
        ax.scatter([float(r['bill_length_mm']) for r in group], [float(r['flipper_length_mm']) for r in group],
                   label=species, color=color, marker=marker, s=26, alpha=.8, edgecolors='white', linewidths=.4)
    ax.set_xlim(30, 61)
    ax.set_ylim(165, 235)
    ax.set_xticks(range(30, 61, 5))
    ax.set_yticks(range(170, 231, 10))
    ax.set_xlabel('Bill length (mm)', fontsize=14, labelpad=13)
    ax.set_title('Flipper length (mm)', fontsize=14, loc='left', pad=14)
    ax.spines[['top', 'right']].set_visible(False)
    ax.spines[['left', 'bottom']].set_color('#aaa4ad')
    ax.tick_params(colors='#514b58', labelsize=12)
    ax.grid(alpha=.12)
    ax.set_axisbelow(True)
    fig.text(.11, .93, 'Penguin measurements', fontsize=23, weight='bold', color='#36283e')
    fig.text(.11, .875, f'{len(complete)} complete measurements', fontsize=13, color='#655c6d')
    ax.legend(loc='lower left', bbox_to_anchor=(-.015, 1.13), ncol=3, frameon=False,
              fontsize=13, handletextpad=.3, columnspacing=1.5)
    png = io.BytesIO()
    fig.savefig(png, format='png')
    plt.close(fig)
    with fitz.open() as doc:
        page = doc.new_page(width=648, height=468)
        page.insert_image(page.rect, stream=png.getvalue())
        assert not page.get_text()  # The input contains pixels, not selectable text.
        doc.save(work / 'penguins-image-original.pdf')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets', type=Path, required=True, help='Directory containing the bundled ONNX model and Korean font')
    parser.add_argument('--work', type=Path, default=ROOT / '.release-work/readme-demo')
    args = parser.parse_args()
    work = args.work.resolve()
    # A fresh directory avoids replacing any previous demonstration or user file.
    work.mkdir(parents=True, exist_ok=False)
    fetch(work)
    os.environ.update(QDT_HOME=str(work / 'profile'), XDG_CACHE_HOME=str(work / 'cache'),
                      QDT_BUNDLED_ASSETS=str(args.assets.resolve()))
    for key in ('GOOGLE_API_KEY', 'GEMINI_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
        os.environ.pop(key, None)
    sys.path[:0] = [str(ROOT / 'services/scholar-translator'), str(ROOT / 'services/mixed-renderer')]

    def no_network(*args, **kwargs):
        raise RuntimeError('The example renderer must not call a remote service.')
    socket.socket.connect = no_network
    socket.create_connection = no_network

    import fitz
    from scholar_translator.doclayout import OnnxModel
    from scholar_translator.high_level import translate

    with fitz.open(work / 'paper.pdf') as source, fitz.open() as excerpt:
        excerpt.insert_pdf(source, from_page=0, to_page=0)
        excerpt.save(work / 'paper-original.pdf')
    chart(work)
    outputs = translate(
        files=[str(work / name) for name in ('paper-original.pdf', 'penguins-image-original.pdf')],
        output=str(work / 'internal'), lang_in='en', lang_out='ko', service='offline', thread=1,
        model=OnnxModel.from_pretrained(), ignore_cache=True,
        envs={'OFFLINE_TRANSLATION_MAP': str(Path(__file__).with_name('translation-map.jsonl'))},
    )
    delivery = work / 'PDF'
    delivery.mkdir()
    images = work / 'images'
    images.mkdir()
    evidence = {'source_commit': '184c074', 'translation': 'recorded Codex agent map', 'samples': {}}
    for name, (mono, dual) in zip(('paper', 'ocr-chart'), outputs):
        shutil.copyfile(dual, delivery / f'{name}-dual-example.pdf')
        with fitz.open(dual) as doc:
            page = doc[0]
            page.get_pixmap(matrix=fitz.Matrix(2400 / page.rect.width, 2400 / page.rect.width)).save(images / f'{name}-dual.png')
            evidence['samples'][name] = {'pages': len(doc), 'size_pt': list(page.rect)}
        if name == 'paper':
            for language, path in [('en', work / 'paper-original.pdf'), ('ko', mono)]:
                with fitz.open(path) as doc:
                    doc[0].get_pixmap(matrix=fitz.Matrix(4, 4), clip=fitz.Rect(82, 214, 279, 429)).save(images / f'paper-abstract-{language}.png')
            with fitz.open(mono) as doc:
                assert all(value in doc[0].get_text() for value in ('98%', '7.3%', '20%'))
        else:
            with fitz.open(work / 'penguins-image-original.pdf') as a, fitz.open(mono) as b:
                region = fitz.Rect(71.3, 135.8, 622, 398)
                before = a[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=region)
                after = b[0].get_pixmap(matrix=fitz.Matrix(2, 2), clip=region)
                assert before.samples == after.samples, 'The plotted data region changed.'
                visible_text = ' '.join(b[0].get_text().split())
                assert all(label in visible_text for label in ('펭귄 측정값', '날개 길이', '부리 길이', '아델리', '턱끈', '젠투', '342'))
                evidence['samples'][name].update(input_native_characters=len(a[0].get_text()), plot_pixels_identical=True)
    (work / 'evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'PDF examples: {delivery}\nREADME images: {images}')


if __name__ == '__main__':
    main()
