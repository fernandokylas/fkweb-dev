---
name: website-assets
description: Collects, directs and records a website's images, logos, icons, illustrations and brand files in the shared assets record, with their source, permitted use, crop, placement and alt text, and keeps unknown-rights or missing assets as visible placeholders rather than invented or downloaded ones. Use it when a site needs imagery, a logo or brand files, when the user supplies photos or a brand kit, asks for stock or AI-generated images, asks whether an image may be used, or when website-design or website-workflow routes asset work here. Works for text-led sites with no assets at all. Not for choosing colours or type (website-design) or for placing files in templates (the build skills).
---

# Website assets

Owns the assets record (`../website-workflow/references/project-records.md`, section Assets). Both build paths read the same record: custom code places the files, WordPress imports them into the media library or the theme. This skill decides what each asset is, where it came from and whether it may be used; it doesn't build pages.

A site with no imagery is valid. Under an `## Assets` heading in the project record, write `- assets: none (<reason>)` and stop; without the heading the record check reports the assets record as missing.

## 1. Inventory what already exists

Read `references/intake.md`. List what the user supplied, what the existing site or repository already holds, and what the brief says is still needed. Every entry gets a source and a permitted use; when nobody has said what the use terms are, `permitted_use` is `unknown`. Tell owner or client material from third-party material (`supplied_by`): only the first can be covered by a standing permission the owner or client grants, recorded once with who granted it and when (`references/intake.md`, "Three kinds of supplied material"). Being supplied is not being authorised.

Don't search the web for a client's logo or product photos, and don't download files from other sites, social profiles or image search. Ask for them, or record them as `needed`.

## 2. Direct the assets that are still needed

Read `references/image-direction.md`. For each needed asset, write what it must show and why, its placement and crop, and how it relates to the direction in the design record. Then choose the route: the user supplies it, an existing licensed library, a stock service or an image generator.

Stock services and generators are optional providers. Calling a paid or external service needs the user's authority for that call; without it, write the brief, mark the asset `needed` (or `placeholder` once a stand-in is in the layout), and continue. The site never depends on a provider being available. The `image-provider` row in `../website-workflow/references/optional-integrations.md` states what such a call costs and sends.

## 3. Prepare and place

Read `references/preparation.md` for formats, sizes, responsive sources, alt text and placeholders. Placeholders keep the final aspect ratio and say plainly that they are placeholders, so the layout doesn't shift when the real file arrives and nobody mistakes them for final content.

## 4. Record and check

Write one `### Asset: <id>` entry per asset with every record field. No field is left empty or holds `TBD`, `TODO` or similar, which the check treats as defects. A field that doesn't apply yet (no `local_path` for a `needed` asset) reads `n/a: <reason>`; a fact nobody has given yet reads `unknown (OPEN-n)`, with the matching item in `state.json` `open_issues`. Then run the record check:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_records.py" check-records docs/website --phase implement
```

It fails a missing or empty field, an unknown status, and an asset marked `approved` while `permitted_use` starts with `unknown`; it warns on `unknown` without an `OPEN-n` reference. It doesn't judge vague wording such as "probably fine" or rights on assets in other statuses, so apply the rule below yourself. After the build, check the record against the files the build uses:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/sw_design_check.py" --site <built-site> --records docs/website --root . --checks assets.rights,assets.local-path
```

It fails unknown rights on an approved asset, a missing credit where the licence asks for one, and a `local_path` that is a URL, absolute, outside the project or missing; it warns on build images the record doesn't list. With `--release` (run by `website-verify`) unknown rights, unrecorded images and unfinished statuses all fail. `media.images` in the static site check confirms every image has an `alt` attribute; whether the alt text is accurate is a manual check in `website-verify`.

An asset with unknown rights is not published as final, whatever its status. Add it to `state.json` `open_issues` as `{id, issue, blocking}` with what resolves it (the supplier's confirmation, a licence, or a replacement), and report it.

Record each route decision (supplied, stock, generated, placeholder) in `state.json` `accepted_decisions` as `{id, decision, reason}`.
