"""WAI-ARIA vocabularies (concrete roles and states/properties).

Sources, checked October 2026:
  * WAI-ARIA 1.2 (w3.org/TR/wai-aria-1.2/) and the ARIA 1.3 editor's draft
    (w3c.github.io/aria/): roles and attributes. 1.3 adds the roles comment,
    image (a synonym of img), mark, sectionfooter, sectionheader and
    suggestion, and the attributes aria-colindextext, aria-rowindextext,
    aria-description and the braille pair. Abstract roles (command, widget,
    landmark and the rest) are for the spec, not for authors, and stay
    unknown here.
  * DPUB-ARIA 1.1 (w3.org/TR/dpub-aria-1.1/, Recommendation, June 2025):
    the doc-* roles Pandoc, Quarto and EPUB tools write, deprecated ones
    included.
  * Graphics-ARIA 1.0 (w3.org/TR/graphics-aria-1.0/): graphics-document,
    graphics-object, graphics-symbol.
Accepting the drafts' additions keeps forward-looking markup from being
reported as unknown.
"""

ROLES = {
    "alert", "alertdialog", "application", "article", "banner", "blockquote",
    "button", "caption", "cell", "checkbox", "code", "columnheader",
    "combobox", "complementary", "contentinfo", "definition", "deletion",
    "dialog", "directory", "document", "emphasis", "feed", "figure", "form",
    "generic", "grid", "gridcell", "group", "heading", "img", "insertion",
    "link", "list", "listbox", "listitem", "log", "main", "marquee", "math",
    "menu", "menubar", "menuitem", "menuitemcheckbox", "menuitemradio",
    "meter", "navigation", "none", "note", "option", "paragraph",
    "presentation", "progressbar", "radio", "radiogroup", "region", "row",
    "rowgroup", "rowheader", "scrollbar", "search", "searchbox", "separator",
    "slider", "spinbutton", "status", "strong", "subscript", "superscript",
    "switch", "tab", "table", "tablist", "tabpanel", "term", "textbox",
    "time", "timer", "toolbar", "tooltip", "tree", "treegrid", "treeitem",
    # WAI-ARIA 1.3 (editor's draft)
    "comment", "image", "mark", "sectionfooter", "sectionheader", "suggestion",
    # DPUB-ARIA 1.1
    "doc-abstract", "doc-acknowledgments", "doc-afterword", "doc-appendix",
    "doc-backlink", "doc-biblioentry", "doc-bibliography", "doc-biblioref",
    "doc-chapter", "doc-colophon", "doc-conclusion", "doc-cover",
    "doc-credit", "doc-credits", "doc-dedication", "doc-endnote",
    "doc-endnotes", "doc-epigraph", "doc-epilogue", "doc-errata",
    "doc-example", "doc-footnote", "doc-foreword", "doc-glossary",
    "doc-glossref", "doc-index", "doc-introduction", "doc-noteref",
    "doc-notice", "doc-pagebreak", "doc-pagefooter", "doc-pageheader",
    "doc-pagelist", "doc-part", "doc-preface", "doc-prologue",
    "doc-pullquote", "doc-qna", "doc-subtitle", "doc-tip", "doc-toc",
    # Graphics-ARIA 1.0
    "graphics-document", "graphics-object", "graphics-symbol",
}

ARIA_ATTRS = {
    "aria-activedescendant", "aria-atomic", "aria-autocomplete",
    "aria-braillelabel", "aria-brailleroledescription", "aria-busy",
    "aria-checked", "aria-colcount", "aria-colindex", "aria-colindextext",
    "aria-colspan",
    "aria-controls", "aria-current", "aria-describedby", "aria-description",
    "aria-details", "aria-disabled", "aria-dropeffect", "aria-errormessage",
    "aria-expanded", "aria-flowto", "aria-grabbed", "aria-haspopup",
    "aria-hidden", "aria-invalid", "aria-keyshortcuts", "aria-label",
    "aria-labelledby", "aria-level", "aria-live", "aria-modal",
    "aria-multiline", "aria-multiselectable", "aria-orientation",
    "aria-owns", "aria-placeholder", "aria-posinset", "aria-pressed",
    "aria-readonly", "aria-relevant", "aria-required",
    "aria-roledescription", "aria-rowcount", "aria-rowindex", "aria-rowindextext",
    "aria-rowspan", "aria-selected", "aria-setsize", "aria-sort",
    "aria-valuemax", "aria-valuemin", "aria-valuenow", "aria-valuetext",
}

#: Roles whose elements are user-interface components that WCAG 4.1.2 (and
#: the ACT name rules c487ae, 97a4e1, e086e5, 23a2a8, m6b1q3) require to
#: have an accessible name. Used to decide when a broken aria-labelledby is
#: a failure (it left such an element unnamed) rather than a review item.
NAME_REQUIRED_ROLES = {
    "button", "checkbox", "combobox", "image", "img", "link", "listbox",
    "menuitem",
    "menuitemcheckbox", "menuitemradio", "option", "radio", "searchbox",
    "slider", "spinbutton", "switch", "tab", "textbox", "treeitem",
}

#: The form fields of ACT rule e086e5 ("Form field has non-empty accessible
#: name"): the roles that inherit from input, menuitem or select and are
#: form field controls. bb-control-label checks every element with one of
#: them, native or by an explicit role.
FORM_FIELD_ROLES = frozenset({
    "checkbox", "combobox", "listbox", "menuitemcheckbox", "menuitemradio",
    "radio", "searchbox", "slider", "spinbutton", "switch", "textbox",
})

#: The roles the name-by-role rules check, one rule for each basis W3C
#: gives an unnamed one (Part R2 review): bb-widget-name the controls W3C
#: failure F68 covers (and an empty tooltip, for review), bb-role-img-name
#: an image made with role=img (ACT 23a2a8), bb-progress-name progress bars
#: and meters (no W3C failure: heuristic).
CONTROL_NAME_ROLES = frozenset({"menuitem", "option", "tab", "treeitem",
                                "tooltip"})
IMG_ROLES = frozenset({"img", "image"})
PROGRESS_ROLES = frozenset({"progressbar", "meter"})
#: All of them: the roles whose elements must be named and that no other
#: name rule owns (bb-link-name, bb-button-name, bb-control-label,
#: bb-img-alt, bb-svg-name). axe-core checks the same roles
#: (aria-command-name's menuitem, aria-tab-name, aria-tooltip-name,
#: aria-treeitem-name, aria-progressbar-name, aria-meter-name,
#: role-img-alt, aria-toggle-field-name's option).
WIDGET_NAME_ROLES = CONTROL_NAME_ROLES | IMG_ROLES | PROGRESS_ROLES

#: Roles whose name may come from their content (WAI-ARIA 1.2 "Name From:
#: contents"). Every other role is named by its author only (aria-label,
#: aria-labelledby, title): the text inside a textbox is its value, not its
#: name, and a progress bar's text is not its label.
NAME_FROM_CONTENT_ROLES = frozenset({
    "button", "cell", "checkbox", "columnheader", "comment", "gridcell",
    "heading", "link", "menuitem", "menuitemcheckbox", "menuitemradio",
    "option", "radio", "row", "rowheader", "sectionfooter", "sectionheader",
    "switch", "tab", "tooltip", "treeitem",
    "doc-backlink", "doc-biblioref", "doc-glossref", "doc-noteref",
})

# Attributes whose value is an ID reference (list) into the same document.
# aria-labeledby is one where aria-labelledby is absent: Chromium 141 reads
# it as aria-labelledby (accname.labelledby_attr).
ID_REF_ATTRS = (
    "aria-labelledby", "aria-labeledby", "aria-describedby",
    "aria-controls", "aria-owns", "aria-activedescendant",
    "aria-errormessage", "aria-details", "aria-flowto",
)
