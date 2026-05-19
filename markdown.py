import curses
import re
import textwrap

# Matches inline spans in priority order: ** before *, __ before _
# Underscore variants require a non-word character boundary so that
# underscores inside identifiers (e.g. count_of_org) are not consumed.
_INLINE_RE = re.compile(
    r'(\*\*(?:.+?)\*\*'            # **bold**
    r'|(?<!\w)__(?:.+?)__(?!\w)'   # __bold__ (word-boundary guarded)
    r'|`(?:.+?)`'                  # `code`
    r'|\*(?:.+?)\*'                # *italic*
    r'|(?<!\w)_(?:.+?)_(?!\w))'    # _italic_ (word-boundary guarded)
)

_HR_RE    = re.compile(r'^[-*_]{3,}\s*$')
_H_RE     = re.compile(r'^(#{1,6})\s+(.*)')
_QUOTE_RE = re.compile(r'^>\s*(.*)')
_UL_RE    = re.compile(r'^[-*+]\s+(.*)')
_OL_RE    = re.compile(r'^(\d+)\.\s+(.*)')
_CODE_RE  = re.compile(r'^( {4}|\t)(.*)')


def _inline_segments(text, base_attr, code_attr):
    """Return [(text, attr)] by parsing inline markdown spans."""
    parts = _INLINE_RE.split(text)
    result = []
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**') and len(part) >= 5:
            result.append((part[2:-2], base_attr | curses.A_BOLD))
        elif part.startswith('__') and part.endswith('__') and len(part) >= 5:
            result.append((part[2:-2], base_attr | curses.A_BOLD))
        elif part.startswith('`') and part.endswith('`') and len(part) >= 3:
            result.append((part[1:-1], code_attr))
        elif part.startswith('*') and part.endswith('*') and len(part) >= 3:
            result.append((part[1:-1], base_attr | curses.A_DIM))
        elif part.startswith('_') and part.endswith('_') and len(part) >= 3:
            result.append((part[1:-1], base_attr | curses.A_DIM))
        else:
            result.append((part, base_attr))
    return result


def _segs_to_cols(start_col, segments, cols):
    """Convert (text, attr) segments into (col, text, attr) triples."""
    result = []
    x = start_col
    for text, attr in segments:
        if x >= cols - 1:
            break
        visible = text[:cols - 1 - x]
        if visible:
            result.append((x, visible, attr))
        x += len(visible)
    return result


def _wrap_to_visual_lines(indent, text, cols, base_attr, code_attr, prefix=None, prefix_attr=None):
    """Word-wrap text and return a list of visual lines as (col,text,attr) triples."""
    wrap_width = max(1, cols - indent - 1)
    wrapped = textwrap.wrap(text, wrap_width) or [text]
    lines = []
    for i, wline in enumerate(wrapped):
        segs = _inline_segments(wline, base_attr, code_attr)
        items = _segs_to_cols(indent, segs, cols)
        if i == 0 and prefix is not None:
            items = [(1, prefix, prefix_attr or base_attr)] + items
        lines.append(items)
    return lines


def body_to_lines(body, cols):
    """
    Pre-render markdown body into a list of visual lines.
    Each visual line is a list of (col, text, attr) triples ready to draw.
    """
    body_attr  = curses.color_pair(4)
    code_attr  = curses.color_pair(1)
    h1_attr    = curses.color_pair(2) | curses.A_BOLD
    h2_attr    = curses.color_pair(3) | curses.A_BOLD
    h3_attr    = curses.color_pair(4) | curses.A_BOLD
    quote_attr = curses.color_pair(5)
    bull_attr  = body_attr | curses.A_BOLD

    result = []

    for raw in body.splitlines():
        # Blank line
        if not raw.strip():
            result.append([])
            continue

        # Horizontal rule
        if _HR_RE.match(raw):
            result.append([(1, '─' * (cols - 2), code_attr)])
            continue

        # Heading
        m = _H_RE.match(raw)
        if m:
            level = len(m.group(1))
            text  = m.group(2)
            attr  = h1_attr if level == 1 else (h2_attr if level == 2 else h3_attr)
            indent = 1 + (level - 1) * 2
            segs = _inline_segments(text, attr, code_attr)
            result.append(_segs_to_cols(indent, segs, cols))
            continue

        # Blockquote
        m = _QUOTE_RE.match(raw)
        if m:
            for vline in _wrap_to_visual_lines(3, m.group(1), cols,
                                               quote_attr, code_attr,
                                               prefix='│ ', prefix_attr=quote_attr):
                result.append(vline)
            continue

        # Unordered list
        m = _UL_RE.match(raw)
        if m:
            for vline in _wrap_to_visual_lines(3, m.group(1), cols,
                                               body_attr, code_attr,
                                               prefix='• ', prefix_attr=bull_attr):
                result.append(vline)
            continue

        # Ordered list
        m = _OL_RE.match(raw)
        if m:
            num, text = m.group(1), m.group(2)
            prefix = f'{num}. '
            for vline in _wrap_to_visual_lines(1 + len(prefix), text, cols,
                                               body_attr, code_attr,
                                               prefix=prefix, prefix_attr=bull_attr):
                result.append(vline)
            continue

        # Indented code block
        m = _CODE_RE.match(raw)
        if m:
            result.append([(1, m.group(2)[:cols - 2], code_attr)])
            continue

        # Plain paragraph — word-wrap + inline
        for vline in _wrap_to_visual_lines(1, raw, cols, body_attr, code_attr):
            result.append(vline)

    return result
