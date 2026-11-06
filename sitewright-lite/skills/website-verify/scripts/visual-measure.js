/*
 * Sitewright visual measurements (check ID visual.measure, method browser).
 *
 * Run inside a rendered page by whatever browser tool the session already has (an evaluate-script call,
 * or a <script> tag in a scratch copy). It measures; it does not judge. Judgement against the design
 * record's layout_rules and spacing tokens is visual.review (method manual), recorded separately.
 *
 *   swVisualMeasure({scale: [0, 4, 8, 16, 24, 32, 48, 64], tolerance: 1, root: "main"})
 *
 * scale      spacing values in px taken from the design record's spacing tokens (optional; without it
 *            no gap is compared and `off_scale` stays empty)
 * tolerance  px allowed either side of a scale value and between edges counted as aligned (default 1)
 * root       selector of the region to measure (default: body)
 *
 *   await swRevealSweep()   scrolls the page to the bottom in steps of max(200px, 70% of the viewport) and back
 *                           to the top, then waits 700 ms, so scroll-triggered reveals and lazy media load before a
 *                           full-page screenshot or a measurement (adapted from Impeccable's reveal sweep,
 *                           Apache-2.0). Run it before full-page captures and before the screen passes; skip it for
 *                           the print pass, which shows what a reader who prints from the top gets. With
 *                           data-sweep="true" the dom output runs it first.
 *
 * Returns (and, when loaded with data-output="dom", also writes into
 * <script type="application/json" id="sw-visual-measure">) one JSON object:
 *   viewport            width and height in CSS px
 *   gaps                vertical gaps between consecutive in-flow siblings, border box to border box
 *                       (container padding is never counted; collapsed margins are what the reader sees)
 *   off_scale           the gaps that match no scale value within the tolerance
 *   heading_rhythm      per heading: the gap above and the gap below; `tighter_above` when the space
 *                       above is smaller than the space below (the heading reads as part of the block
 *                       before it)
 *   alignment           per container with three or more children: left edges grouped within the
 *                       tolerance, and the children whose edge is in neither the container's content
 *                       edge nor the most common group
 *   grid_items          per grid container: column tracks, in-flow children, generated ::before/::after
 *                       boxes that occupy cells, rows used, and the first child's offset from the
 *                       content edge
 *   tracking            per element with its own visible text and letter spacing above 0.05em or below
 *                       -0.03em: its path, tag, classes, font size, letter spacing in em, text-transform,
 *                       font-variant-caps and own text length (at most 200 rows; `tracking_more` counts the
 *                       rest). It settles the role of rules sw_design_check.py could not classify (class-only
 *                       selectors such as .intro): long text is running text, a few uppercase words a label
 *   tells               repeated template devices inside root, counted, never judged: `eyebrows` (short
 *                       uppercase labels at 15px or less tracked 0.06em or more), `numbering` (01, 02, 03 used as
 *                       labels), `trailing_arrows` (links and buttons whose text ends in an arrow) and `card_kit`
 *                       (one border radius + box shadow pair on several boxes). Each has a count, up to 3
 *                       samples and `repeated` (3 or more; 4 or more for card_kit). Heuristics after Huashu's
 *                       design lint (MIT); whether a device is intended is the design record's call
 *   components          page-wide: the computed look of the shared parts, so page types can be compared:
 *                       `header`, `nav` and `footer` (the first banner, navigation and contentinfo element, or
 *                       null), `buttons` (button-like controls grouped by style, most used first, at most 8
 *                       groups) and `cta_panels` (sections with a heading and a button on their own background,
 *                       at most 5). Each has a `style` (height, colours, font, padding, radius, border,
 *                       shadow) and a short `digest` of it: equal digests on two pages mean the part looks the
 *                       same; heights may differ with content and are left out of the digest
 *   overflow            page-wide (not limited to root): how far the page scrolls sideways past the
 *                       viewport (`amount`, 0 when it fits) and the deepest elements that stick out past the
 *                       right edge without an ancestor that clips them (`culprits`, at most 5)
 *   clipped             elements whose overflow is hidden or clipped (or that end in an ellipsis) and that cut
 *                       off part of their own text: the axis, the px hidden, whether an ellipsis or a line
 *                       clamp shows it on purpose, and the start of the text (at most 50)
 *   edge_text           text runs (3+ characters, under 40px) that sit inside the viewport but closer to its
 *                       left or right edge than `edge_margin` (12px below 600px wide, otherwise 16px; adapted
 *                       from the taste-skill layout rules, MIT): side, px from the edge, start of the text
 *   framed_media        images, video, canvas, svg and iframes that are the only content of a frame (a parent
 *                       with a border, background or shadow): the four insets inside the frame's border and
 *                       `unequal` when opposite insets differ by more than the tolerance (the bottom gap of an
 *                       inline image is the usual cause)
 *   invisible_text      text inside root that is in the layout but not drawn: an ancestor at opacity 0, visibility
 *                       hidden, every line cut away by clipping ancestors, or placed off the page. Each row has the
 *                       reason, the character count and the start of the text (at most 50; `invisible_more` counts
 *                       the rest). Skipped: display none, [hidden], aria-hidden, closed <details> and dialogs,
 *                       panels an aria-expanded="false" control collapses, and screen-reader-only helpers.
 *                       Measured in whatever media the browser emulates (`media`: print, colour scheme, reduced
 *                       motion) and after swRevealSweep() when `swept` is true (claude-blog hidden-text gate
 *                       concept, MIT)
 * Limitations: one viewport per call (run it at each width the review needs); elements hidden or
 * outside the root are skipped; text inside a box is not measured.
 */
(function () {
  "use strict";

  function label(el) {
    if (!el || el.nodeType !== 1) return "";
    var out = el.tagName.toLowerCase();
    if (el.id) return out + "#" + el.id;
    var cls = (el.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (cls.length) out += "." + cls.join(".");
    var parent = el.parentElement;
    if (parent) {
      var same = Array.prototype.filter.call(parent.children, function (c) { return c.tagName === el.tagName; });
      if (same.length > 1) out += ":nth-of-type(" + (same.indexOf(el) + 1) + ")";
    }
    return out;
  }

  function path(el, root) {
    var parts = [];
    for (var n = el; n && n !== root && parts.length < 4; n = n.parentElement) parts.unshift(label(n));
    return parts.join(" > ");
  }

  function inFlow(el) {
    var cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    if (cs.position === "absolute" || cs.position === "fixed") return false;
    if (cs.float !== "none") return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 || r.height > 0;
  }

  function generated(el, which) {
    var cs = getComputedStyle(el, which);
    var content = cs.content;
    if (!content || content === "none" || content === "normal") return false;
    if (cs.display === "none" || cs.position === "absolute" || cs.position === "fixed") return false;
    return true;
  }

  function round(n) { return Math.round(n * 10) / 10; }

  function ownText(el) {
    return Array.prototype.filter.call(el.childNodes, function (n) { return n.nodeType === 3; })
      .map(function (n) { return n.textContent; }).join("").replace(/\s+/g, " ").trim();
  }

  // the box drawn by an element's own text nodes (not its padding), or null
  function ownTextBox(el) {
    var box = null, range = document.createRange();
    Array.prototype.forEach.call(el.childNodes, function (n) {
      if (n.nodeType !== 3 || !n.textContent.trim()) return;
      range.selectNodeContents(n);
      Array.prototype.forEach.call(range.getClientRects(), function (r) {
        if (r.width < 1 || r.height < 1) return;
        if (!box) box = { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
        else {
          box.left = Math.min(box.left, r.left); box.right = Math.max(box.right, r.right);
          box.top = Math.min(box.top, r.top); box.bottom = Math.max(box.bottom, r.bottom);
        }
      });
    });
    return box;
  }

  // screen-reader-only helpers (1px boxes, clip: rect(0 0 0 0)) are not visible text
  function visuallyHidden(el) {
    for (var n = el; n && n !== document.body; n = n.parentElement) {
      var cs = getComputedStyle(n);
      if (cs.display === "none" || cs.visibility === "hidden") return true;
      var r = n.getBoundingClientRect();
      if (cs.overflow !== "visible" && (r.width <= 1 || r.height <= 1)) return true;
      if (cs.clip && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(cs.clip)) return true;
    }
    return false;
  }

  function componentsMeasure() {
    var props = ["backgroundColor", "color", "fontFamily", "fontSize", "fontWeight", "letterSpacing", "textTransform",
                 "paddingTop", "paddingRight", "paddingBottom", "paddingLeft", "borderTopLeftRadius",
                 "borderTopWidth", "borderTopStyle", "borderTopColor", "borderBottomWidth", "borderBottomColor",
                 "boxShadow"];
    function digest(text) {                         // FNV-1a, 32 bit, as 8 hex digits
      var h = 0x811c9dc5;
      for (var k = 0; k < text.length; k++) { h ^= text.charCodeAt(k); h = Math.imul(h, 0x01000193) >>> 0; }
      return ("0000000" + h.toString(16)).slice(-8);
    }
    function look(el) {
      var cs = getComputedStyle(el), style = {};
      props.forEach(function (p) { style[p.replace(/[A-Z]/g, function (c) { return "_" + c.toLowerCase(); })] = cs[p]; });
      return style;
    }
    function shown(el) {
      if (!el || !el.getClientRects().length) return false;
      var cs = getComputedStyle(el);
      return cs.visibility !== "hidden" && cs.display !== "none";
    }
    function part(el) {
      if (!shown(el)) return null;
      var style = look(el);
      return { element: path(el, document.body), height: round(el.getBoundingClientRect().height),
               style: style, digest: digest(JSON.stringify(style)) };
    }
    function first(selector, notInside) {
      var list = document.querySelectorAll(selector);
      for (var k = 0; k < list.length; k++) {
        if (notInside && list[k].closest(notInside)) continue;
        if (shown(list[k])) return list[k];
      }
      return null;
    }
    var bodyBg = getComputedStyle(document.body).backgroundColor;
    var buttonSel = "button, input[type=submit], input[type=button], [role=button], a.button, a.btn, a[class*='button'], a[class*='btn']";
    var groups = {};
    Array.prototype.forEach.call(document.querySelectorAll(buttonSel + ", a"), function (el) {
      if (!shown(el)) return;
      if (!el.matches(buttonSel)) {                  // a plain link counts when it is drawn as a button
        var cs = getComputedStyle(el);
        var filled = cs.backgroundColor !== "rgba(0, 0, 0, 0)" && cs.backgroundColor !== "transparent";
        var boxed = parseFloat(cs.borderTopWidth) > 0 && cs.borderTopStyle !== "none" && parseFloat(cs.paddingLeft) >= 8;
        if (!filled && !boxed) return;
      }
      var style = look(el), key = digest(JSON.stringify(style));
      if (!groups[key]) groups[key] = { digest: key, count: 0, style: style, sample: path(el, document.body), heights: [] };
      groups[key].count += 1;
      var h = round(el.getBoundingClientRect().height);
      if (groups[key].heights.indexOf(h) < 0 && groups[key].heights.length < 4) groups[key].heights.push(h);
    });
    var buttons = Object.keys(groups).map(function (k) { return groups[k]; })
      .sort(function (a, b) { return b.count - a.count; }).slice(0, 8);
    var panels = [];
    Array.prototype.forEach.call(document.querySelectorAll("main section, main aside, main div, [class*='cta']"), function (el) {
      if (panels.length >= 5 || !shown(el)) return;
      var bg = getComputedStyle(el).backgroundColor;
      var own = bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent" && bg !== bodyBg;
      if (!(own || /cta/i.test(el.className || ""))) return;
      if (!el.querySelector("h1, h2, h3, h4") || !el.querySelector(buttonSel + ", a")) return;
      if (panels.some(function (p) { return p.node.contains(el); })) return;
      var row = part(el); row.node = el; panels.push(row);
    });
    panels.forEach(function (p) { delete p.node; });
    return { header: part(first("header, [role=banner]", "main, article, section")),
             nav: part(first("nav, [role=navigation]")),
             footer: part(first("footer, [role=contentinfo]", "main, article, section")),
             buttons: buttons, cta_panels: panels };
  }

  // Template-device counts after Huashu's design lint (scripts/design_lint.py, MIT): re-implemented, counts only.
  function tellsMeasure(all) {
    function bucket(min) { return { count: 0, samples: [], repeated: false, min: min }; }
    var t = { eyebrows: bucket(3), numbering: bucket(3), trailing_arrows: bucket(3) }, kits = {};
    function note(b, text) { b.count += 1; if (b.samples.length < 3) b.samples.push(text.slice(0, 30)); }
    all.forEach(function (el) {
      if (!el.getClientRects().length) return;
      var cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || parseFloat(cs.opacity) <= 0.05) return;
      var own = ownText(el);
      if (own) {
        var size = parseFloat(cs.fontSize) || 16;
        var spacing = cs.letterSpacing === "normal" ? 0 : (parseFloat(cs.letterSpacing) || 0) / size;
        var latin = own.replace(/[^A-Za-z]/g, "");
        var caps = cs.textTransform === "uppercase" || (latin.length >= 3 && latin === latin.toUpperCase());
        if (caps && latin.length >= 2 && own.length <= 40 && spacing >= 0.06 && size <= 15) note(t.eyebrows, own);
        if (/^0\d(?:[\s./—-]|$)/.test(own) && own.length <= 6) note(t.numbering, own);
        if (/[→↗⟶]\s*$/.test(own) && el.closest("a, button")) note(t.trailing_arrows, own);
      }
      if (cs.boxShadow !== "none" && parseFloat(cs.borderTopLeftRadius) > 0) {
        var sig = cs.borderTopLeftRadius + " | " + cs.boxShadow;
        if (!kits[sig]) kits[sig] = { radius: cs.borderTopLeftRadius, shadow: cs.boxShadow, count: 0, sample: null };
        kits[sig].count += 1;
        if (!kits[sig].sample) kits[sig].sample = el;
      }
    });
    Object.keys(t).forEach(function (k) { t[k].repeated = t[k].count >= t[k].min; delete t[k].min; });
    var top = Object.keys(kits).map(function (k) { return kits[k]; })
      .sort(function (a, b) { return b.count - a.count; })[0];
    t.card_kit = top ? { count: top.count, radius: top.radius, shadow: top.shadow, repeated: top.count >= 4,
                         sample: path(top.sample, document.body) }
                     : { count: 0, radius: null, shadow: null, repeated: false, sample: null };
    return t;
  }

  // Adapted from Impeccable's reveal sweep (crates/browser/src/lib.rs, Apache-2.0): step down the page so
  // on-scroll reveals and lazy media fire, return to the top and let transitions settle.
  function revealSweep() {
    var step = Math.max(200, Math.floor(window.innerHeight * 0.7));
    var max = Math.max(document.documentElement.scrollHeight || 0, document.body ? document.body.scrollHeight : 0);
    var y = 0, steps = 0;
    function frame() {
      // a frame then 40 ms; the timer alone also resolves it where frames are throttled (headless, background tab)
      return new Promise(function (resolve) {
        var done = false;
        function finish() { if (!done) { done = true; resolve(); } }
        requestAnimationFrame(function () { setTimeout(finish, 40); });
        setTimeout(finish, 120);
      });
    }
    function next() {
      if (y > max) {
        window.scrollTo(0, 0);
        return new Promise(function (resolve) { setTimeout(resolve, 700); }).then(function () {
          window.__swSwept = true;
          return { steps: steps, step_px: step, height: max };
        });
      }
      window.scrollTo(0, y);
      y += step; steps += 1;
      return frame().then(next);
    }
    return next();
  }

  function mediaState() {
    function m(q) { return window.matchMedia ? window.matchMedia(q).matches : false; }
    return { print: m("print"), color_scheme: m("(prefers-color-scheme: dark)") ? "dark" : "light",
             reduced_motion: m("(prefers-reduced-motion: reduce)") };
  }

  function invisibleMeasure(root) {
    var rows = [], more = 0, owners = new Map();
    var docW = document.documentElement.scrollWidth, docH = document.documentElement.scrollHeight;
    var collapsed = Array.prototype.map.call(document.querySelectorAll("[aria-expanded='false'][aria-controls]"),
      function (c) { return c.getAttribute("aria-controls"); }).join(" ").split(/\s+/).filter(Boolean);
    function skipped(el) {
      if (el.closest("template, noscript, script, style, [hidden], [aria-hidden='true'], dialog:not([open])")) return true;
      var d = el.closest("details:not([open])");
      if (d && !(el.closest("summary") && el.closest("summary").parentElement === d)) return true;
      return collapsed.some(function (id) { var t = document.getElementById(id); return t && t.contains(el); });
    }
    function reasonFor(node, el) {
      for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
        var cs = getComputedStyle(n);
        if (cs.display === "none") return null;                  // removed on purpose, not "invisible"
      }
      for (var h = el; h && h !== document.body; h = h.parentElement) {
        // a 1px or rect(0) box is a screen-reader helper, not text meant to be seen
        var hs = getComputedStyle(h), hr = h.getBoundingClientRect();
        if (hs.position === "absolute" && hs.overflow !== "visible" && (hr.width <= 1 || hr.height <= 1)) return null;
        if (hs.clip && /rect\(0(px)?,? 0(px)?,? 0(px)?,? 0(px)?\)/.test(hs.clip)) return null;
      }
      for (var a = el; a && a.nodeType === 1; a = a.parentElement) {
        if (parseFloat(getComputedStyle(a).opacity) <= 0.05) return "opacity";
      }
      if (getComputedStyle(el).visibility === "hidden") return "visibility";
      var range = document.createRange();
      range.selectNodeContents(node);
      var rects = Array.prototype.filter.call(range.getClientRects(), function (r) { return r.width >= 1 && r.height >= 1; });
      if (!rects.length) return null;
      var sx = window.scrollX, sy = window.scrollY;
      if (rects.every(function (r) { return r.right + sx <= 0 || r.bottom + sy <= 0 || r.left + sx >= docW || r.top + sy >= docH; })) {
        // moved away by a transform (a reveal waiting to slide in); a box positioned off the page without
        // one is the old screen-reader helper (left: -9999px)
        for (var t = el; t && t.nodeType === 1; t = t.parentElement) {
          if (getComputedStyle(t).transform !== "none") return "offscreen";
        }
        return null;
      }
      var shown = rects.some(function (r) {
        var box = { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
        for (var p = el; p && p !== document.documentElement; p = p.parentElement) {
          var cs = getComputedStyle(p);
          var pr = p.getBoundingClientRect();
          if (/hidden|clip/.test(cs.overflowX) || /hidden|clip/.test(cs.overflowY)) {
            var inner = { left: pr.left + p.clientLeft, top: pr.top + p.clientTop };
            inner.right = inner.left + p.clientWidth; inner.bottom = inner.top + p.clientHeight;
            if (/hidden|clip/.test(cs.overflowX)) { box.left = Math.max(box.left, inner.left); box.right = Math.min(box.right, inner.right); }
            if (/hidden|clip/.test(cs.overflowY)) { box.top = Math.max(box.top, inner.top); box.bottom = Math.min(box.bottom, inner.bottom); }
          }
          if (cs.clipPath && /inset\(\s*(50%|100%)/.test(cs.clipPath)) return false;
          if (box.right - box.left < 1 || box.bottom - box.top < 1) return false;
        }
        return true;
      });
      return shown ? null : "clipped";
    }
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    for (var node = walker.nextNode(); node; node = walker.nextNode()) {
      var text = node.textContent.replace(/\s+/g, " ").trim();
      var el = node.parentElement;
      if (!text || !el || skipped(el)) continue;
      var reason = reasonFor(node, el);
      if (!reason) continue;
      var entry = owners.get(el);
      if (!entry) {
        if (rows.length >= 50) { more += 1; continue; }
        entry = { element: path(el, root.parentElement), reason: reason, chars: 0, text: text.slice(0, 40) };
        owners.set(el, entry);
        rows.push(entry);
      }
      entry.chars += text.length;
    }
    return { rows: rows, more: more };
  }

  function overflowMeasure() {
    var W = document.documentElement.clientWidth;
    var amount = Math.max(0, document.documentElement.scrollWidth - W);
    var res = { viewport_width: W, scroll_width: document.documentElement.scrollWidth,
                amount: amount > 2 ? amount : 0, culprits: [] };
    if (!res.amount) return res;
    function clippedAbove(el) {
      for (var p = el.parentElement; p && p !== document.body && p !== document.documentElement; p = p.parentElement) {
        if (getComputedStyle(p).overflowX !== "visible" && p.getBoundingClientRect().right <= W + 2) return true;
      }
      return false;
    }
    var wide = Array.prototype.filter.call(document.body.querySelectorAll("*"), function (el) {
      if (/^(SCRIPT|STYLE|TEMPLATE)$/.test(el.tagName)) return false;
      var r = el.getBoundingClientRect();
      return r.width > 0 && r.right > W + 2 && !clippedAbove(el);
    });
    res.culprits = wide.filter(function (el) {
      return !wide.some(function (o) { return o !== el && el.contains(o); });
    }).slice(0, 5).map(function (el) {
      var r = el.getBoundingClientRect();
      return { element: path(el, document.body), width: round(r.width), right: round(r.right),
               past_edge: round(r.right - W) };
    });
    return res;
  }

  function clippedMeasure(all, root, tol) {
    var rows = [];
    all.forEach(function (el) {
      if (rows.length >= 50 || !(el instanceof HTMLElement)) return;
      var cs = getComputedStyle(el);
      var clipX = /hidden|clip/.test(cs.overflowX), clipY = /hidden|clip/.test(cs.overflowY);
      var ellipsis = cs.textOverflow === "ellipsis";
      if (!clipX && !clipY && !ellipsis) return;
      if (el.clientWidth <= 1 || el.clientHeight <= 1 || visuallyHidden(el)) return;
      if (el.scrollWidth <= el.clientWidth + tol && el.scrollHeight <= el.clientHeight + tol) return;
      var box = el.getBoundingClientRect();
      var inner = { left: box.left + el.clientLeft, top: box.top + el.clientTop };
      inner.right = inner.left + el.clientWidth; inner.bottom = inner.top + el.clientHeight;
      var hx = 0, hy = 0, text = "";
      var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT), range = document.createRange(), seen = 0;
      for (var n = walker.nextNode(); n && seen < 200; n = walker.nextNode()) {
        if (!n.textContent.trim()) continue;
        seen += 1;
        range.selectNodeContents(n);
        Array.prototype.forEach.call(range.getClientRects(), function (r) {
          if (r.width < 1 || r.height < 1) return;
          var x = Math.max(0, r.right - inner.right, inner.left - r.left);
          var y = Math.max(0, r.bottom - inner.bottom, inner.top - r.top);
          if ((clipX || ellipsis) && x > tol) { hx = Math.max(hx, x); if (!text) text = n.textContent; }
          if (clipY && y > tol) { hy = Math.max(hy, y); if (!text) text = n.textContent; }
        });
      }
      if (!hx && !hy) return;
      var clamp = parseInt(cs.webkitLineClamp || cs.lineClamp, 10);
      rows.push({ element: path(el, root.parentElement), axis: hx && hy ? "both" : hx ? "x" : "y",
                  hidden_px: round(Math.max(hx, hy)), ellipsis: ellipsis, line_clamp: isNaN(clamp) ? null : clamp,
                  text: text.replace(/\s+/g, " ").trim().slice(0, 40) });
    });
    return rows;
  }

  function edgeTextMeasure(all, root) {
    var W = document.documentElement.clientWidth, margin = W < 600 ? 12 : 16, rows = [];
    all.forEach(function (el) {
      if (rows.length >= 20 || !(el instanceof HTMLElement)) return;
      var own = ownText(el);
      if (own.length < 3 || el.closest("table, marquee, [class*='marquee' i], [class*='ticker' i]")) return;
      var cs = getComputedStyle(el);
      if ((parseFloat(cs.fontSize) || 16) >= 40 || visuallyHidden(el)) return;
      var b = ownTextBox(el);
      if (!b || b.left < -1 || b.right > W + 1) return;            // off the screen: overflow or a bleed
      var left = b.left, right = W - b.right;
      if (left >= margin && right >= margin) return;
      rows.push({ element: path(el, root.parentElement), side: left < right ? "left" : "right",
                  px: round(Math.min(left, right)), text: own.slice(0, 30) });
    });
    return { edge_margin: margin, rows: rows };
  }

  function framedMediaMeasure(root, tol) {
    var rows = [];
    Array.prototype.forEach.call(root.querySelectorAll("img, video, canvas, svg, iframe, picture"), function (m) {
      if (rows.length >= 50 || (m.tagName === "IMG" && m.parentElement && m.parentElement.tagName === "PICTURE")) return;
      if (m.tagName.toLowerCase() === "svg" && m.parentElement && m.parentElement.closest("svg")) return;
      var frame = m.parentElement;
      if (!frame || frame === root.parentElement) return;
      var others = Array.prototype.filter.call(frame.children, function (c) {
        return c !== m && !/^(SCRIPT|STYLE|TEMPLATE)$/.test(c.tagName) && inFlow(c);
      });
      if (others.length || ownText(frame)) return;
      var cs = getComputedStyle(frame);
      var bordered = ["Top", "Right", "Bottom", "Left"].some(function (s) {
        return parseFloat(cs["border" + s + "Width"]) > 0 && cs["border" + s + "Style"] !== "none";
      });
      var filled = cs.backgroundColor && !/rgba\(0, 0, 0, 0\)|transparent/.test(cs.backgroundColor);
      var shadow = cs.boxShadow && cs.boxShadow !== "none";
      if (!bordered && !filled && !shadow) return;
      var f = frame.getBoundingClientRect(), r = m.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) return;
      var insets = { top: round(r.top - f.top - parseFloat(cs.borderTopWidth)),
                     right: round(f.right - parseFloat(cs.borderRightWidth) - r.right),
                     bottom: round(f.bottom - parseFloat(cs.borderBottomWidth) - r.bottom),
                     left: round(r.left - f.left - parseFloat(cs.borderLeftWidth)) };
      rows.push({ frame: path(frame, root.parentElement), media: m.tagName.toLowerCase(), insets: insets,
                  unequal: Math.abs(insets.top - insets.bottom) > tol || Math.abs(insets.left - insets.right) > tol });
    });
    return rows;
  }

  function nearest(scale, value) {
    var best = null;
    scale.forEach(function (s) { if (best === null || Math.abs(s - value) < Math.abs(best - value)) best = s; });
    return best;
  }

  function measure(config) {
    config = config || {};
    var tol = typeof config.tolerance === "number" ? config.tolerance : 1;
    var scale = (config.scale || []).map(Number).filter(function (n) { return !isNaN(n); });
    var root = document.querySelector(config.root || "body") || document.body;
    var out = {
      tool: "visual-measure", version: "2",
      viewport: { width: window.innerWidth, height: window.innerHeight },
      root: config.root || "body", scale: scale, tolerance: tol,
      gaps: [], off_scale: [], heading_rhythm: [], alignment: [], grid_items: [], tracking: [], tracking_more: 0,
      overflow: null, clipped: [], edge_text: [], edge_margin: null, framed_media: [],
      media: mediaState(), swept: !!window.__swSwept, invisible_text: [], invisible_more: 0, tells: null, components: null
    };
    var all = [root].concat(Array.prototype.slice.call(root.querySelectorAll("*")));
    var headingGaps = new Map();

    all.forEach(function (container) {
      if (!(container instanceof HTMLElement) || /^(SCRIPT|STYLE|TEMPLATE|svg)$/i.test(container.tagName)) return;
      var cs = getComputedStyle(container);
      if (cs.display === "none") return;
      var kids = Array.prototype.filter.call(container.children, function (c) {
        return !/^(SCRIPT|STYLE|TEMPLATE)$/.test(c.tagName) && inFlow(c);
      });
      var where = path(container, root.parentElement);
      var box = container.getBoundingClientRect();
      var contentLeft = box.left + parseFloat(cs.borderLeftWidth) + parseFloat(cs.paddingLeft);

      // vertical gaps between consecutive siblings that stack (block flow, or one-column grid/flex)
      for (var i = 1; i < kids.length; i++) {
        var a = kids[i - 1].getBoundingClientRect(), b = kids[i].getBoundingClientRect();
        if (b.top < a.bottom - tol) continue;                 // side by side, not stacked
        var gap = round(b.top - a.bottom);
        var item = { container: where, from: label(kids[i - 1]), to: label(kids[i]), gap: gap };
        out.gaps.push(item);
        if (scale.length) {
          var near = nearest(scale, gap);
          if (Math.abs(near - gap) > tol) out.off_scale.push({ container: where, from: item.from, to: item.to,
                                                              gap: gap, nearest: near });
        }
        if (/^H[1-6]$/.test(kids[i].tagName)) {
          headingGaps.set(kids[i], Object.assign(headingGaps.get(kids[i]) || {}, { above: gap }));
        }
        if (/^H[1-6]$/.test(kids[i - 1].tagName)) {
          headingGaps.set(kids[i - 1], Object.assign(headingGaps.get(kids[i - 1]) || {}, { below: gap }));
        }
      }

      // left-edge alignment of the children
      if (kids.length >= 3 && !/grid|flex/.test(cs.display)) {
        var groups = {};
        kids.forEach(function (k) {
          var x = round(k.getBoundingClientRect().left);
          var key = Object.keys(groups).find(function (g) { return Math.abs(Number(g) - x) <= tol; });
          key = key === undefined ? String(x) : key;
          (groups[key] = groups[key] || []).push(label(k));
        });
        var keys = Object.keys(groups);
        if (keys.length > 1) {
          var common = keys.reduce(function (m, k) { return groups[k].length > groups[m].length ? k : m; }, keys[0]);
          var outliers = [];
          keys.forEach(function (k) {
            if (k === common || Math.abs(Number(k) - contentLeft) <= tol) return;
            groups[k].forEach(function (name) {
              outliers.push({ child: name, left: Number(k), offset_from_common: round(Number(k) - Number(common)) });
            });
          });
          out.alignment.push({ container: where, content_left: round(contentLeft),
                               edges: keys.map(function (k) { return { left: Number(k), children: groups[k] }; }),
                               outliers: outliers });
        }
      }

      // grid containers: tracks, items and generated boxes that take cells
      if (/grid/.test(cs.display)) {
        var tracks = cs.gridTemplateColumns && cs.gridTemplateColumns !== "none"
          ? cs.gridTemplateColumns.trim().split(/\s+/).length : 1;
        var gen = ["::before", "::after"].filter(function (w) { return generated(container, w); });
        var cells = kids.length + gen.length;
        var first = kids.length ? kids[0].getBoundingClientRect() : null;
        var tops = [];
        kids.forEach(function (k) {
          var t = round(k.getBoundingClientRect().top);
          if (!tops.some(function (x) { return Math.abs(x - t) <= tol; })) tops.push(t);
        });
        out.grid_items.push({ container: where, display: cs.display, column_tracks: tracks,
                              children: kids.length, generated_items: gen, cells_used: cells,
                              rows_used: tops.length,
                              first_child_offset: first ? round(first.left - contentLeft) : null });
      }
    });

    all.forEach(function (el) {
      var own = ownText(el);
      if (!own || !el.getClientRects().length) return;
      var cs = getComputedStyle(el);
      if (cs.visibility === "hidden") return;
      var size = parseFloat(cs.fontSize) || 16;
      var spacing = cs.letterSpacing === "normal" ? 0 : parseFloat(cs.letterSpacing) || 0;
      var em = Math.round(spacing / size * 1000) / 1000;
      if (em <= 0.05 && em >= -0.03) return;
      if (out.tracking.length >= 200) { out.tracking_more += 1; return; }
      out.tracking.push({ element: path(el, root.parentElement), tag: el.tagName.toLowerCase(),
                          classes: Array.prototype.slice.call(el.classList), font_size_px: round(size),
                          letter_spacing_em: em, text_transform: cs.textTransform,
                          font_variant_caps: cs.fontVariantCaps, text_length: own.length });
    });

    headingGaps.forEach(function (g, el) {
      var row = { heading: path(el, root.parentElement), above: g.above === undefined ? null : g.above,
                  below: g.below === undefined ? null : g.below };
      row.tighter_above = row.above !== null && row.below !== null && row.above + tol < row.below;
      out.heading_rhythm.push(row);
    });

    out.overflow = overflowMeasure();
    out.clipped = clippedMeasure(all, root, tol);
    var edge = edgeTextMeasure(all, root);
    out.edge_margin = edge.edge_margin;
    out.edge_text = edge.rows;
    out.framed_media = framedMediaMeasure(root, tol);
    var hidden = invisibleMeasure(root);
    out.invisible_text = hidden.rows;
    out.invisible_more = hidden.more;
    out.tells = tellsMeasure(all);
    out.components = componentsMeasure();
    return out;
  }

  window.swVisualMeasure = measure;
  window.swRevealSweep = revealSweep;
  var me = document.currentScript;
  if (me && me.dataset.output === "dom") {
    var config = {};
    if (me.dataset.scale) config.scale = me.dataset.scale.split(",").map(Number);
    if (me.dataset.root) config.root = me.dataset.root;
    if (me.dataset.tolerance) config.tolerance = Number(me.dataset.tolerance);
    var write = function () {
      var result;
      try { result = measure(config); } catch (e) { result = { tool: "visual-measure", error: String(e) }; }
      var node = document.createElement("script");
      node.type = "application/json";
      node.id = "sw-visual-measure";
      node.textContent = JSON.stringify(result);
      document.body.appendChild(node);
    };
    if (me.dataset.sweep === "true") revealSweep().then(write, write);
    else write();
  }
})();
