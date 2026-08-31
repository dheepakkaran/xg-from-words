"""Turn the post into something Medium will actually accept.

Medium has never supported tables. Pasted Markdown tables break outright, and
pasted HTML tables get flattened. Everything else -- headings, bold, lists,
code blocks, quotes -- survives if you paste *rendered* content rather than
Markdown source.

So this does two things:

  * rewrites every table as a monospace block, which Medium keeps and which
    holds column alignment (narrow ones) or as a bold-label list (the wide
    glossary, which would scroll off a phone as a code block);
  * renders the result to a single HTML file you open, select all, copy, and
    paste straight into the Medium editor.

Run it after editing MEDIUM_POST.md. Nothing here is done by hand, so the two
files cannot drift.
"""
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "MEDIUM_POST.md")
OUT_MD = os.path.join(HERE, "MEDIUM_POST_medium-safe.md")
OUT_HTML = os.path.join(HERE, "medium-paste.html")
# A second copy without the instruction box, published on GitHub Pages so
# Medium's URL importer can read it. Pasting needs the clipboard, which the
# automation surface here is not allowed to touch; importing needs only a URL.
OUT_IMPORT = os.path.join(HERE, "..", "docs", "post.html")

# A code block wider than this scrolls sideways on a phone.
MAX_WIDTH = 62


def split_row(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def is_divider(line):
    return bool(re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line)) and "-" in line


def as_block(head, rows):
    """Table as aligned monospace. Returns None if it will not fit."""
    cols = list(zip(*([head] + rows)))
    widths = [max(len(strip_md(c)) for c in col) for col in cols]
    if sum(widths) + 2 * (len(widths) - 1) > MAX_WIDTH:
        return None
    out = []
    for i, row in enumerate([head] + rows):
        cells = []
        for j, c in enumerate(row):
            t = strip_md(c)
            cells.append(t.rjust(widths[j]) if j else t.ljust(widths[j]))
        out.append("  ".join(cells).rstrip())
        if i == 0:
            out.append("  ".join("-" * w for w in widths))
    return "```\n" + "\n".join(out) + "\n```"


def as_list(head, rows):
    """Table as a bold-label list, for anything too wide to align.

    Repeating the column heading in every row -- "Full name: x, What it means
    here: y" -- reads like a form. The first column becomes the label, the
    second the thing it stands for, and the rest is prose.
    """
    out = []
    for row in rows:
        cells = [strip_md(c) for c in row]
        label, rest = cells[0], [c for c in cells[1:] if c not in ("", "—")]
        if not rest:
            out.append(f"**{label}**")
        elif len(rest) == 1:
            out.append(f"**{label}** — {rest[0]}")
        else:
            tail = " ".join(r if r.endswith(".") else r + "." for r in rest[1:])
            out.append(f"**{label}** — *{rest[0]}*. {tail}")
    return "\n\n".join(out)


def strip_md(text):
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.strip()


def convert_tables(md):
    lines, out, i, changed = md.split("\n"), [], 0, 0
    while i < len(lines):
        if (lines[i].strip().startswith("|") and i + 1 < len(lines)
                and is_divider(lines[i + 1])):
            head = split_row(lines[i])
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(split_row(lines[i]))
                i += 1
            block = as_block(head, rows) or as_list(head, rows)
            out.append(block)
            changed += 1
            continue
        out.append(lines[i])
        i += 1
    return "\n".join(out), changed


INLINE = [
    (r"`([^`]+)`", r"<code>\1</code>"),
    (r"\*\*([^*]+)\*\*", r"<strong>\1</strong>"),
    (r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>"),
    (r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>'),
]


def inline(text):
    text = html.escape(text, quote=False)
    for pat, rep in INLINE:
        text = re.sub(pat, rep, text)
    return text


def to_html(md):
    out, i, lines = [], 0, md.split("\n")
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            i += 1
            buf = []
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(html.escape(lines[i], quote=False))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        if re.fullmatch(r"\s*---+\s*", line):
            out.append("<hr>")
        elif m := re.match(r"(#{1,4})\s+(.*)", line):
            n = len(m.group(1))
            out.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif line.startswith("> "):
            buf = []
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(inline(lines[i][2:]))
                i += 1
            out.append("<blockquote><p>" + " ".join(buf) + "</p></blockquote>")
            continue
        elif re.match(r"\s*[-*]\s+", line):
            buf = []
            while i < len(lines) and re.match(r"\s*[-*]\s+", lines[i]):
                # Anchored, once. Unanchored it also matched the "* " inside a
                # closing "**", so "- **The numbers.** Count" rendered as
                # "**The numbers.*Count".
                buf.append("<li>"
                           + inline(re.sub(r"^\s*[-*]\s+", "", lines[i], count=1))
                           + "</li>")
                i += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        elif re.match(r"\s*\d+\.\s+", line):
            buf = []
            while i < len(lines) and re.match(r"\s*\d+\.\s+", lines[i]):
                buf.append("<li>"
                           + inline(re.sub(r"^\s*\d+\.\s+", "", lines[i], count=1))
                           + "</li>")
                i += 1
            out.append("<ol>" + "".join(buf) + "</ol>")
            continue
        elif line.strip():
            buf = []
            while (i < len(lines) and lines[i].strip()
                   and not re.match(r"(#|>|```|\s*[-*]\s|\s*\d+\.\s|\s*---+\s*$)",
                                    lines[i])):
                buf.append(inline(lines[i]))
                i += 1
            out.append("<p>" + " ".join(buf) + "</p>")
            continue
        i += 1
    return "\n".join(out)


PAGE = """<!doctype html>
<meta charset="utf-8">
<title>Medium paste — xg-from-words</title>
<style>
 /* Forced light, not inherited. This page exists to be read and copied, and a
    dark system theme was rendering #222 text on a dark background. */
 :root {{ color-scheme: light; }}
 html, body {{ background: #ffffff; }}
 body {{ max-width: 42rem; margin: 3rem auto; padding: 0 1.25rem;
        font: 18px/1.65 Georgia, "Times New Roman", serif; color: #222; }}
 h1 {{ font-size: 2.1rem; line-height: 1.2; }}
 h2 {{ font-size: 1.5rem; margin-top: 2.4rem; }}
 h3 {{ font-size: 1.2rem; margin-top: 1.8rem; }}
 pre {{ background: #f6f6f4; padding: .9rem 1rem; overflow-x: auto;
       font: 13px/1.5 ui-monospace, Menlo, monospace; border-radius: 6px; }}
 code {{ font: .88em ui-monospace, Menlo, monospace; background: #f2f2f0;
        padding: .08em .3em; border-radius: 3px; }}
 pre code {{ background: none; padding: 0; }}
 blockquote {{ margin: 1.4rem 0; padding-left: 1.1rem;
              border-left: 3px solid #ddd; color: #444; font-style: italic; }}
 hr {{ border: 0; border-top: 1px solid #e5e5e2; margin: 2.4rem 0; }}
 /* user-select:none keeps this box out of a Cmd+A, so selecting the whole
    page selects only the story. */
 .how {{ background: #fffbe6; border: 1px solid #f0e3a0; padding: 1rem 1.2rem;
        font-family: system-ui, sans-serif; font-size: .9rem; border-radius: 8px;
        user-select: none; -webkit-user-select: none; }}
</style>
<div class="how">
 <strong>Cmd&nbsp;+&nbsp;A, then Cmd&nbsp;+&nbsp;C.</strong> This box is
 excluded from the selection, so you get the story and nothing else.
 <br><br>
 In the Medium draft: click in the body, <em>Cmd&nbsp;+&nbsp;A</em>,
 <em>Cmd&nbsp;+&nbsp;V</em>. That replaces everything with this version.
 Headings, bold, lists, quotes and code blocks all survive; tables were
 rewritten as code blocks and lists, because Medium has none. Add a cover
 image at the top afterwards.
</div>
{body}
"""


IMPORT_PAGE = """<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>I tried to predict football goals from commentary. I failed, and that
failure led somewhere better.</title>
<meta name="description" content="A story about expected goals, four hidden
bugs, and a robot that watches football so I do not have to.">
<meta name="author" content="Dheepak Karan">
<style>
 :root {{ color-scheme: light; }}
 html, body {{ background: #fff; }}
 body {{ max-width: 42rem; margin: 3rem auto; padding: 0 1.25rem;
        font: 18px/1.65 Georgia, "Times New Roman", serif; color: #222; }}
 pre {{ background: #f6f6f4; padding: .9rem 1rem; overflow-x: auto;
       font: 13px/1.5 ui-monospace, Menlo, monospace; }}
 code {{ font: .88em ui-monospace, Menlo, monospace; }}
 blockquote {{ margin: 1.4rem 0; padding-left: 1.1rem;
              border-left: 3px solid #ddd; font-style: italic; }}
</style>
<article>
{body}
</article>
</html>
"""


def main():
    md = open(SRC).read()
    safe, n = convert_tables(md)
    open(OUT_MD, "w").write(safe)
    body = to_html(safe)
    open(OUT_HTML, "w").write(PAGE.format(body=body))
    open(OUT_IMPORT, "w").write(IMPORT_PAGE.format(body=body))
    remaining = safe.count("\n|")
    print(f"{n} tables rewritten")
    print(f"markdown tables left: {remaining} (should be 0)")
    print(f"  {os.path.relpath(OUT_MD)}")
    print(f"  {os.path.relpath(OUT_HTML)}")
    print(f"  {os.path.relpath(OUT_IMPORT)}   (for Medium's URL importer)")
    if remaining:
        sys.exit("a table survived the conversion")


if __name__ == "__main__":
    main()
