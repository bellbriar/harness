"""Fix guidance for every rule that runs (A6): why it matters, how to fix
it, and short examples in HTML (before and after), React and Vue.

The HTML report shows the guidance of each rule it has findings for, and
docs/RULES.md (tools/make_rules_reference.py) shows all of it beside the
rulebook's own fields. The guidance is kept apart from rulebook.json on
purpose: the rulebook decides verdicts and is identified by its digest in
reports and signed bundles, while this text can be improved in any release
without changing what a run decides or what a bundle records.

The HTML examples are executable: tests/test_part_r3.py runs each rule on
its `bad` example, which must give a finding of that rule, and on its
`good` example, which must give none (a rule that only asks for review may
still ask, at minor impact, where `good_still_reviews` says so) and no FAIL
of any rule. `where` says how an example sits in the page the test builds
(EXAMPLE_PAGES); the React and Vue examples show the same fix in each
framework's own syntax and are reviewed by hand.
"""
from __future__ import annotations

#: How an HTML example becomes the page the test evaluates: {x} is the
#: example. "body" (the default) puts it in the page's <main>; "page" in
#: <body>, before any <main>; "head" in <head>; "html" is the <html> start
#: tag itself; "head-element" the whole <head>; "body-element" the whole
#: <body>.
EXAMPLE_PAGES = {
    "body": ('<!doctype html><html lang="en"><head><title>Example</title>'
             '</head><body><main><h1>Example</h1>{x}</main></body></html>'),
    "page": ('<!doctype html><html lang="en"><head><title>Example</title>'
             '</head><body>{x}</body></html>'),
    "head": ('<!doctype html><html lang="en"><head><title>Example</title>{x}'
             '</head><body><main><h1>Example</h1></main></body></html>'),
    "html": ('<!doctype html>{x}<head><title>Example</title></head><body>'
             '<main><h1>Example</h1></main></body></html>'),
    "head-element": ('<!doctype html><html lang="en">{x}<body><main>'
                     '<h1>Example</h1></main></body></html>'),
    "body-element": ('<!doctype html><html lang="en"><head><title>Example'
                     '</title></head>{x}</html>'),
}


def example_page(text: str, where: str = "body") -> str:
    """The page an HTML example is evaluated in (EXAMPLE_PAGES)."""
    return EXAMPLE_PAGES[where].replace("{x}", text)


#: {rule id: guidance}. Every implemented static and rendered rule has an
#: entry (tests/test_part_r3.py); the judged rules, not in 1.0, have none.
GUIDANCE: dict[str, dict] = {
    # ------------------------------------------------------------ names
    "bb-img-alt": {
        "why": "A screen reader cannot describe an image that has no text "
               "alternative: it reads out the file name or skips the "
               "image, so what it shows is lost to people who cannot see "
               "it.",
        "fix": "Give every image that carries information an alt "
               "attribute that says what it shows or does. Give a purely "
               "decorative image an empty alt (alt=\"\"), so screen readers "
               "skip it.",
        "html_bad": '<img src="team.jpg">',
        "html_good": '<img src="team.jpg" alt="Our five-person support team">',
        "react": '<img src={teamPhoto} alt="Our five-person support team" />',
        "vue": '<img :src="teamPhoto" alt="Our five-person support team">',
    },
    "bb-svg-name": {
        "why": "An <svg> marked role=\"img\" is announced as an image, and "
               "its drawing is not read: without a name, users hear only "
               "\"image\".",
        "fix": "Name it with aria-label, or with a <title> as its first "
               "child that aria-labelledby points to. If the graphic is "
               "decorative, drop role=\"img\" and add aria-hidden=\"true\" "
               "instead.",
        "html_bad": '<svg role="img" viewBox="0 0 24 24">\n'
                    '  <path d="M3 12h18"/>\n</svg>',
        "html_good": '<svg role="img" aria-label="Rated 4 out of 5" '
                     'viewBox="0 0 24 24">\n  <path d="M3 12h18"/>\n</svg>',
        "react": '<svg role="img" aria-label="Rated 4 out of 5" '
                 'viewBox="0 0 24 24">\n  <path d="M3 12h18" />\n</svg>',
        "vue": '<svg role="img" :aria-label="`Rated ${rating} out of 5`" '
               'viewBox="0 0 24 24">\n  <path d="M3 12h18" />\n</svg>',
    },
    "bb-link-name": {
        "why": "A link with no text is announced as just \"link\", or by "
               "its address, so screen-reader users cannot tell where it "
               "goes, and voice-control users have no name to say to "
               "follow it.",
        "fix": "Give every link text that says where it goes. For a link "
               "that shows only an icon, add aria-label (or visually "
               "hidden text) and hide the icon with aria-hidden=\"true\".",
        "html_bad": '<a href="/cart">\n'
                    '  <svg aria-hidden="true" viewBox="0 0 24 24">'
                    '<path d="M3 3h18"/></svg>\n</a>',
        "html_good": '<a href="/cart" aria-label="Shopping cart">\n'
                     '  <svg aria-hidden="true" viewBox="0 0 24 24">'
                     '<path d="M3 3h18"/></svg>\n</a>',
        "react": '<a href="/cart" aria-label="Shopping cart">\n'
                 '  <CartIcon aria-hidden="true" />\n</a>',
        "vue": '<a href="/cart" aria-label="Shopping cart">\n'
               '  <CartIcon aria-hidden="true" />\n</a>',
    },
    "bb-button-name": {
        "why": "A button with no name is announced as just \"button\", so "
               "screen-reader users cannot tell what it does.",
        "fix": "Put text in the button. For a button that shows only an "
               "icon, add aria-label and hide the icon with "
               "aria-hidden=\"true\".",
        "html_bad": '<button type="button">\n'
                    '  <svg aria-hidden="true" viewBox="0 0 24 24">'
                    '<path d="M6 6l12 12"/></svg>\n</button>',
        "html_good": '<button type="button" aria-label="Close dialog">\n'
                     '  <svg aria-hidden="true" viewBox="0 0 24 24">'
                     '<path d="M6 6l12 12"/></svg>\n</button>',
        "react": '<button type="button" aria-label="Close dialog" '
                 'onClick={onClose}>\n  <XIcon aria-hidden="true" />\n'
                 '</button>',
        "vue": '<button type="button" aria-label="Close dialog" '
               '@click="close">\n  <XIcon aria-hidden="true" />\n</button>',
    },
    "bb-redundant-links": {
        "why": "Two links in a row to the same page, such as a product "
               "image and its title, make keyboard and screen-reader users "
               "pass the same destination twice. Complaints plead this as "
               "\"redundant links\"; it is not a WCAG failure on its own.",
        "fix": "Combine them into one link (W3C technique H2): put the "
               "image and the text in a single <a>, and give the image "
               "alt=\"\" so the name is not read twice.",
        "html_bad": '<a href="/shoes/red"><img src="red.jpg" '
                    'alt="Red sneaker"></a>\n'
                    '<a href="/shoes/red">Red sneaker</a>',
        "html_good": '<a href="/shoes/red">\n'
                     '  <img src="red.jpg" alt=""> Red sneaker\n</a>',
        "react": '<a href={`/shoes/${shoe.slug}`}>\n'
                 '  <img src={shoe.image} alt="" /> {shoe.name}\n</a>',
        "vue": '<a :href="`/shoes/${shoe.slug}`">\n'
               '  <img :src="shoe.image" alt=""> {{ shoe.name }}\n</a>',
    },
    "bb-control-label": {
        "why": "A form field with no accessible name is announced only by "
               "its type (\"edit text\"), so screen-reader users cannot "
               "tell what to enter.",
        "fix": "Give each field a visible <label> tied to it (for and id, "
               "or the field inside the label). Where no visible label "
               "fits, use aria-label or aria-labelledby. A placeholder is "
               "not a label: it disappears as the user types.",
        "html_bad": '<input type="email" name="email">',
        "html_good": '<label for="email">Email</label>\n'
                     '<input type="email" id="email" name="email">',
        "react": '<>\n'
                 '  <label htmlFor="email">Email</label>\n'
                 '  <input type="email" id="email" value={email}\n'
                 '    onChange={(e) => setEmail(e.target.value)} />\n'
                 '</>',
        "vue": '<label for="email">Email</label>\n'
               '<input id="email" v-model="email" type="email">',
    },
    "bb-widget-name": {
        "why": "A menu item, option, tab or tree item with no name is "
               "announced only by its role, so users cannot tell it from "
               "the others.",
        "fix": "Give each one visible text, or aria-label when it shows "
               "only an icon or a color. A custom widget such as this "
               "listbox also needs the keyboard support of its WAI-ARIA "
               "pattern (here, arrow keys that move "
               "aria-activedescendant).",
        "html_bad": '<div role="listbox" aria-label="Color" tabindex="0"\n'
                    '  aria-activedescendant="color-red">\n'
                    '  <span role="option" id="color-red" '
                    'aria-selected="true"\n'
                    '    class="swatch red"></span>\n</div>',
        "html_good": '<div role="listbox" aria-label="Color" tabindex="0"\n'
                     '  aria-activedescendant="color-red">\n'
                     '  <span role="option" id="color-red" '
                     'aria-selected="true"\n'
                     '    class="swatch red" aria-label="Red"></span>\n'
                     '</div>',
        "react": '<span role="option" id={`color-${color.id}`} '
                 'aria-selected={selected}\n'
                 '  className={`swatch ${color.id}`} '
                 'aria-label={color.name} />',
        "vue": '<span role="option" :id="`color-${color.id}`" '
               ':aria-selected="selected"\n'
               '  :class="[\'swatch\', color.id]" '
               ':aria-label="color.name"></span>',
    },
    "bb-role-img-name": {
        "why": "An element marked role=\"img\" is announced as an image, "
               "and its content is not read: without a name, users hear "
               "only \"image\".",
        "fix": "Name it with aria-label or aria-labelledby. If it is "
               "decorative, remove role=\"img\" and hide it with "
               "aria-hidden=\"true\".",
        "html_bad": '<span role="img" class="icon-warning"></span>',
        "html_good": '<span role="img" class="icon-warning" '
                     'aria-label="Warning"></span>',
        "react": '<span role="img" className="icon-warning" '
                 'aria-label="Warning" />',
        "vue": '<span role="img" class="icon-warning" '
               'aria-label="Warning"></span>',
    },
    "bb-progress-name": {
        "why": "A progress bar or meter with no name has its value read "
               "out (\"40%\") without saying what it measures.",
        "fix": "Name it with aria-label or aria-labelledby, such as "
               "aria-label=\"Upload progress\".",
        "html_bad": '<div role="progressbar" aria-valuenow="40" '
                    'aria-valuemin="0"\n  aria-valuemax="100"></div>',
        "html_good": '<div role="progressbar" aria-valuenow="40" '
                     'aria-valuemin="0"\n  aria-valuemax="100" '
                     'aria-label="Upload progress"></div>',
        "react": '<div role="progressbar" aria-valuenow={percent} '
                 'aria-valuemin={0}\n  aria-valuemax={100} '
                 'aria-label="Upload progress" />',
        "vue": '<div role="progressbar" :aria-valuenow="percent" '
               'aria-valuemin="0"\n  aria-valuemax="100" '
               'aria-label="Upload progress"></div>',
    },
    "bb-control-role": {
        "why": "An element that takes keyboard focus but whose role names "
               "no ARIA role (a typo such as role=\"buton\") has no role "
               "at all: screen readers cannot say what it is or how to "
               "use it.",
        "fix": "Use the native element (<button>, <a href>, <input>), or "
               "spell the role correctly and add the keyboard handling it "
               "needs.",
        "html_bad": '<div role="buton" tabindex="0">Save</div>',
        "html_good": '<button type="button">Save</button>',
        "react": '<button type="button" onClick={save}>Save</button>',
        "vue": '<button type="button" @click="save">Save</button>',
    },
    # ------------------------------------------------------------- page
    "bb-html-lang": {
        "why": "Screen readers choose their voice and pronunciation from "
               "the page's language. Without a valid lang on <html> they "
               "may read the page with the wrong language's rules.",
        "fix": "Set lang on the <html> element to the page's main "
               "language, as a valid tag such as \"en\", \"en-US\" or "
               "\"es\".",
        "where": "html",
        "html_bad": '<html>',
        "html_good": '<html lang="en">',
        "react": '// app/layout.jsx (Next.js); in a Vite app, set it in '
                 'index.html\nexport default function RootLayout'
                 '({ children }) {\n  return (\n    <html lang="en">\n'
                 '      <body>{children}</body>\n    </html>\n  );\n}',
        "vue": '<!-- index.html (Vite); in Nuxt, app.head.htmlAttrs in '
               'nuxt.config -->\n<html lang="en">',
    },
    "bb-page-title": {
        "why": "The page title is the first thing a screen reader "
               "announces and what names the browser tab. Without one, "
               "users cannot tell pages apart.",
        "fix": "Give every page a <title> that names the page, then the "
               "site (\"Pricing - Acme\"). In a single-page app, change it "
               "on every route.",
        "where": "head-element",
        "html_bad": '<head>\n  <meta charset="utf-8">\n</head>',
        "html_good": '<head>\n  <meta charset="utf-8">\n'
                     '  <title>Pricing - Acme</title>\n</head>',
        "react": '// React 19 renders a <title> in a component into <head>\n'
                 'function PricingPage() {\n  return (\n    <>\n'
                 '      <title>Pricing - Acme</title>\n'
                 '      <h1>Pricing</h1>\n    </>\n  );\n}',
        "vue": '// router.js (Vue Router)\nrouter.afterEach((to) => {\n'
               '  document.title = to.meta.title ? `${to.meta.title} - Acme`'
               ' : \'Acme\'\n})',
    },
    "bb-skip-link": {
        "why": "Without a way past the header and navigation, keyboard "
               "and screen-reader users must go through every one of "
               "their links on every page before they reach the content.",
        "fix": "Make the first link on the page a \"Skip to main content\" "
               "link to the main content's id; it may stay visually "
               "hidden until it receives focus. Wrap the content in "
               "<main> too, which screen readers can jump to.",
        "where": "page",
        "html_bad": '<header>\n  <nav>\n    <a href="/">Home</a> '
                    '<a href="/shop">Shop</a> <a href="/about">About</a>\n'
                    '  </nav>\n</header>\n'
                    '<div class="content"><p>Fresh bread every '
                    'morning.</p></div>',
        "html_good": '<a href="#main" class="skip-link">Skip to main '
                     'content</a>\n<header>\n  <nav>\n'
                     '    <a href="/">Home</a> <a href="/shop">Shop</a> '
                     '<a href="/about">About</a>\n  </nav>\n</header>\n'
                     '<main id="main"><h1>Welcome</h1>'
                     '<p>Fresh bread every morning.</p></main>',
        "react": '<>\n'
                 '  <a href="#main" className="skip-link">Skip to main content</a>\n'
                 '  <SiteHeader />\n'
                 '  <main id="main">{children}</main>\n'
                 '</>',
        "vue": '<a href="#main" class="skip-link">Skip to main content</a>\n'
               '<SiteHeader />\n<main id="main"><RouterView /></main>',
    },
    "bb-viewport-zoom": {
        "why": "People with low vision zoom in on phones. A viewport that "
               "blocks zoom (user-scalable=no, or a maximum-scale below "
               "2) takes that away.",
        "fix": "Use width=device-width, initial-scale=1, and remove "
               "user-scalable=no and maximum-scale.",
        "where": "head",
        "html_bad": '<meta name="viewport"\n  content="width=device-width, '
                    'initial-scale=1, maximum-scale=1, user-scalable=no">',
        "html_good": '<meta name="viewport" content="width=device-width, '
                     'initial-scale=1">',
        "react": '// app/layout.jsx (Next.js): no maximumScale or '
                 'userScalable\nexport const viewport = '
                 '{ width: \'device-width\', initialScale: 1 };',
        "vue": '<!-- index.html -->\n<meta name="viewport" '
               'content="width=device-width, initial-scale=1">',
    },
    "bb-aria-ref": {
        "why": "aria-labelledby, aria-describedby, aria-controls, <label "
               "for> and the other references point at ids. One that "
               "points at no id gives assistive technology nothing to "
               "follow: the name, description or controlled panel it was "
               "meant to give is silently lost.",
        "fix": "Make every reference name an id that exists on the page. "
               "In components, generate the ids (React's useId, Vue's "
               "useId) so the two stay in step.",
        "html_bad": '<input type="search" aria-label="Search"\n'
                    '  aria-describedby="search-help">',
        "html_good": '<input type="search" aria-label="Search"\n'
                     '  aria-describedby="search-help">\n'
                     '<p id="search-help">Search by name or order '
                     'number.</p>',
        "react": 'const helpId = useId();\nreturn (\n  <>\n'
                 '    <input type="search" aria-label="Search" '
                 'aria-describedby={helpId} />\n'
                 '    <p id={helpId}>Search by name or order number.</p>\n'
                 '  </>\n);',
        "vue": '<script setup>\nimport { useId } from \'vue\'\n'
               'const helpId = useId()\n</script>\n<template>\n'
               '  <input type="search" aria-label="Search" '
               ':aria-describedby="helpId">\n'
               '  <p :id="helpId">Search by name or order number.</p>\n'
               '</template>',
    },
    "bb-aria-hidden-focus": {
        "why": "aria-hidden=\"true\" hides content from screen readers, "
               "but a link or button inside it can still take keyboard "
               "focus: users land on something that is announced as "
               "nothing.",
        "fix": "Never put focusable content inside aria-hidden. Take "
               "content that is not in use out of use for everyone: the "
               "hidden attribute or display: none, or inert where it must "
               "stay visible (a carousel's other slides); otherwise remove "
               "aria-hidden.",
        "html_bad": '<div class="slide" aria-hidden="true">\n'
                    '  <a href="/sale">Summer sale</a>\n</div>',
        "html_good": '<div class="slide" hidden>\n'
                     '  <a href="/sale">Summer sale</a>\n</div>',
        "react": '<div className="slide" hidden={!active}>\n'
                 '  <a href="/sale">Summer sale</a>\n</div>',
        "vue": '<div class="slide" :hidden="!active">\n'
               '  <a href="/sale">Summer sale</a>\n</div>',
    },
    "bb-positive-tabindex": {
        "why": "A positive tabindex pulls an element ahead of the page's "
               "natural order, so keyboard users jump around in an order "
               "that no longer matches what they see.",
        "fix": "Remove positive tabindex values. Put elements in the "
               "source in the order they should be reached; use "
               "tabindex=\"0\" only to make a custom control focusable.",
        "html_bad": '<button type="button" tabindex="3">Subscribe</button>',
        "html_good": '<button type="button">Subscribe</button>',
        "react": '<button type="button" onClick={subscribe}>Subscribe'
                 '</button>',
        "vue": '<button type="button" @click="subscribe">Subscribe'
               '</button>',
    },
    "bb-marquee-blink": {
        "why": "Text that keeps moving with no way to pause it distracts "
               "people with attention difficulties and is hard to read "
               "for people with low vision.",
        "fix": "Replace <marquee> with static text. If something must "
               "move, stop it within five seconds or give it a visible "
               "pause button.",
        "html_bad": '<marquee>Free delivery on orders over $50</marquee>',
        "html_good": '<p class="promo">Free delivery on orders over $50</p>',
        "react": '<p className="promo">Free delivery on orders over $50</p>',
        "vue": '<p class="promo">Free delivery on orders over $50</p>',
    },
    "bb-aria-role": {
        "why": "Assistive technology ignores a role it does not know, so "
               "a misspelt or invented role says nothing about the "
               "element.",
        "fix": "Use a role WAI-ARIA defines, spelled exactly, or none: "
               "native elements already have the right role.",
        "html_bad": '<ul role="lsit">\n  <li>Rye</li>\n  <li>Sourdough</li>\n'
                    '</ul>',
        "html_good": '<ul>\n  <li>Rye</li>\n  <li>Sourdough</li>\n</ul>',
        "react": '<ul>\n  {loaves.map((loaf) => <li key={loaf.id}>'
                 '{loaf.name}</li>)}\n</ul>',
        "vue": '<ul>\n  <li v-for="loaf in loaves" :key="loaf.id">'
               '{{ loaf.name }}</li>\n</ul>',
    },
    "bb-aria-attr": {
        "why": "A misspelt ARIA attribute does nothing, so the state or "
               "name it was meant to give never reaches users.",
        "fix": "Spell ARIA attributes exactly as WAI-ARIA defines them "
               "(aria-expanded, aria-label, aria-describedby).",
        "html_bad": '<button type="button" aria-expnaded="false">Menu'
                    '</button>',
        "html_good": '<button type="button" aria-expanded="false">Menu'
                     '</button>',
        "react": '<button type="button" aria-expanded={open} '
                 'onClick={toggle}>Menu</button>',
        "vue": '<button type="button" :aria-expanded="open" '
               '@click="toggle">Menu</button>',
    },
    "bb-duplicate-id": {
        "why": "A label or ARIA reference finds the first element with an "
               "id. When two elements share it, the second field gets the "
               "first one's label, or none.",
        "fix": "Make every id unique on the page. In components that "
               "render more than once, generate the id (React's useId, "
               "Vue's useId) instead of writing it in.",
        "html_bad": '<label for="qty">Quantity</label> '
                    '<input id="qty" type="number">\n'
                    '<label for="qty">Quantity</label> '
                    '<input id="qty" type="number">',
        "html_good": '<label for="qty-1">Quantity</label> '
                     '<input id="qty-1" type="number">\n'
                     '<label for="qty-2">Quantity</label> '
                     '<input id="qty-2" type="number">',
        "react": 'function QuantityField() {\n  const id = useId();\n'
                 '  return (\n    <>\n'
                 '      <label htmlFor={id}>Quantity</label>\n'
                 '      <input id={id} type="number" />\n    </>\n  );\n}',
        "vue": '<script setup>\nimport { useId } from \'vue\'\n'
               'const id = useId()\n</script>\n<template>\n'
               '  <label :for="id">Quantity</label>\n'
               '  <input :id="id" type="number">\n</template>',
    },
    "bb-heading-structure": {
        "why": "Screen-reader users move through a page by its headings. "
               "An empty heading is announced as nothing, and a missing "
               "h1 or skipped levels make the outline harder to follow.",
        "fix": "Give each page one h1 that names its content, put text in "
               "every heading, and go down one level at a time; choose a "
               "heading's level by its place in the outline and its size "
               "with CSS.",
        "html_bad": '<h2><span class="icon-star"></span></h2>',
        "html_good": '<h2>Featured loaves</h2>',
        "react": '{section.title && <h2>{section.title}</h2>}',
        "vue": '<h2 v-if="section.title">{{ section.title }}</h2>',
    },
    "bb-table-headers": {
        "why": "Without header cells a screen reader reads a data table "
               "as a run of values, with no column or row names to say "
               "what each one is.",
        "fix": "Mark header cells with <th>, with scope=\"col\" or "
               "scope=\"row\". A table used only for layout takes "
               "role=\"presentation\"; better, lay it out with CSS.",
        "html_bad": '<table>\n  <tr><td>Plan</td><td>Price</td>'
                    '<td>Seats</td></tr>\n'
                    '  <tr><td>Basic</td><td>$10</td><td>1</td></tr>\n'
                    '  <tr><td>Team</td><td>$40</td><td>5</td></tr>\n'
                    '</table>',
        "html_good": '<table>\n  <tr><th scope="col">Plan</th>'
                     '<th scope="col">Price</th><th scope="col">Seats</th>'
                     '</tr>\n'
                     '  <tr><td>Basic</td><td>$10</td><td>1</td></tr>\n'
                     '  <tr><td>Team</td><td>$40</td><td>5</td></tr>\n'
                     '</table>',
        "react": '<table>\n  <thead>\n    <tr><th scope="col">Plan</th>'
                 '<th scope="col">Price</th></tr>\n  </thead>\n  <tbody>\n'
                 '    {plans.map((p) => (\n      <tr key={p.id}>'
                 '<td>{p.name}</td><td>{p.price}</td></tr>\n    ))}\n'
                 '  </tbody>\n</table>',
        "vue": '<table>\n  <thead>\n    <tr><th scope="col">Plan</th>'
               '<th scope="col">Price</th></tr>\n  </thead>\n  <tbody>\n'
               '    <tr v-for="p in plans" :key="p.id"><td>{{ p.name }}'
               '</td><td>{{ p.price }}</td></tr>\n  </tbody>\n</table>',
    },
    "bb-iframe-title": {
        "why": "Screen readers announce a frame by its name. An unnamed "
               "frame (a map, a video, a booking form) gives no hint of "
               "what is inside before users enter it.",
        "fix": "Give every iframe a title that says what it holds, such "
               "as title=\"Map of our store\".",
        "html_bad": '<iframe src="https://maps.example.com/embed?store=12">'
                    '</iframe>',
        "html_good": '<iframe src="https://maps.example.com/embed?store=12"\n'
                     '  title="Map of our store"></iframe>',
        "react": '<iframe src={mapUrl} title="Map of our store" />',
        "vue": '<iframe :src="mapUrl" title="Map of our store"></iframe>',
    },
    "bb-media-autoplay": {
        "why": "Sound that starts by itself talks over a screen reader, "
               "and a user who cannot find how to stop it may not be able "
               "to use the page.",
        "fix": "Do not play sound automatically: let users start it. "
               "Media that must start by itself should be muted, with "
               "visible controls.",
        "html_bad": '<video src="promo.mp4" autoplay></video>',
        "html_good": '<video src="promo.mp4" controls>\n'
                     '  <track kind="captions" src="promo.en.vtt" '
                     'srclang="en" label="English">\n</video>',
        "react": '<video src={promoUrl} controls>\n'
                 '  <track kind="captions" src={captionsUrl} srcLang="en" '
                 'label="English" />\n</video>',
        "vue": '<video :src="promoUrl" controls>\n'
               '  <track kind="captions" :src="captionsUrl" srclang="en" '
               'label="English">\n</video>',
    },
    "bb-media-captions": {
        "why": "Deaf and hard-of-hearing people need captions for speech "
               "and sound, and blind people need the visuals described "
               "where they carry information the audio does not.",
        "fix": "Add a captions track to every video with speech or "
               "meaningful sound, put a transcript beside audio, and "
               "offer an audio-described version where the visuals carry "
               "information. Embed only captioned sources.",
        "html_bad": '<video src="tour.mp4" controls></video>',
        "html_good": '<video src="tour.mp4" controls>\n'
                     '  <track kind="captions" src="tour.en.vtt" '
                     'srclang="en" label="English">\n</video>',
        # A captioned video still asks, at minor impact, whether it
        # needs audio description (1.2.5): only a person can tell.
        "good_still_reviews": "bb-media-captions",
        "react": '<video src={tourUrl} controls>\n'
                 '  <track kind="captions" src={captionsUrl} srcLang="en" '
                 'label="English" />\n</video>',
        "vue": '<video :src="tourUrl" controls>\n'
               '  <track kind="captions" :src="captionsUrl" srclang="en" '
               'label="English">\n</video>',
    },
    "bb-autocomplete": {
        "why": "An autocomplete token tells browsers and assistive tools "
               "what a field asks for, so they can fill it in: that helps "
               "people with motor or memory difficulties.",
        "fix": "On fields that ask for the user's own details, add the "
               "matching token: email, tel, name, street-address, "
               "postal-code and so on.",
        "html_bad": '<form>\n  <label for="em">Email</label>\n'
                    '  <input type="email" id="em">\n</form>',
        "html_good": '<form>\n  <label for="em">Email</label>\n'
                     '  <input type="email" id="em" autocomplete="email">\n'
                     '</form>',
        "react": '<input type="email" id="em" autoComplete="email" '
                 'value={email}\n'
                 '  onChange={(e) => setEmail(e.target.value)} />',
        "vue": '<input id="em" v-model="email" type="email" '
               'autocomplete="email">',
    },
    "bb-meta-refresh": {
        "why": "A page that reloads or redirects on a timer can move on "
               "before someone has finished reading or filling it in, "
               "and a screen reader starts again from the top.",
        "fix": "Remove the timed refresh. Redirect on the server (an HTTP "
               "301 or 302), and let users ask for fresh content with a "
               "button.",
        "where": "head",
        "html_bad": '<meta http-equiv="refresh" content="30">',
        "html_good": '<!-- No timed refresh: redirect on the server, or '
                     'offer an Update button -->',
        "react": '<button type="button" onClick={reload}>Show latest '
                 'prices</button>',
        "vue": '<button type="button" @click="reload">Show latest prices'
               '</button>',
    },
    "bb-doc-links": {
        "why": "PDFs and Office files are often not accessible, and this "
               "harness does not check inside them; inaccessible "
               "documents are pled in complaints.",
        "fix": "Publish the content as an HTML page where you can. Send "
               "the documents you must keep for accessibility "
               "remediation, and say in the link what the file is.",
        "html_bad": '<a href="/menu.pdf">Menu</a>',
        "html_good": '<a href="/menu">Menu</a>',
        "react": '<a href="/menu">Menu</a>',
        "vue": '<RouterLink to="/menu">Menu</RouterLink>',
    },
    "bb-a11y-statement": {
        "why": "Settlements with the Department of Justice and private "
               "plaintiffs routinely require an accessibility statement "
               "with a way to report barriers; it also gives users a "
               "route when something does not work.",
        "fix": "Link an accessibility statement from every page, usually "
               "in the footer, saying how to report a barrier and how "
               "soon you will respond.",
        "where": "page",
        "html_bad": '<footer>\n  <a href="/privacy">Privacy</a>\n</footer>',
        "html_good": '<footer>\n  <a href="/privacy">Privacy</a>\n'
                     '  <a href="/accessibility">Accessibility</a>\n'
                     '</footer>',
        "react": '<footer>\n  <a href="/privacy">Privacy</a>\n'
                 '  <a href="/accessibility">Accessibility</a>\n</footer>',
        "vue": '<footer>\n  <RouterLink to="/privacy">Privacy</RouterLink>\n'
               '  <RouterLink to="/accessibility">Accessibility'
               '</RouterLink>\n</footer>',
    },
    "bb-alt-junk": {
        "why": "Alt text that is a file name or a placeholder "
               "(\"IMG_1234.jpg\", \"image\") is read out as it is, so "
               "users still do not learn what the image shows.",
        "fix": "Write alt text that says what the image shows or does, "
               "or alt=\"\" for a decorative image. Check what your CMS "
               "or build tools fill in when no alt text was written.",
        "html_bad": '<img src="IMG_1234.jpg" alt="IMG_1234.jpg">',
        "html_good": '<img src="IMG_1234.jpg" alt="Rye loaves cooling on a '
                     'rack">',
        "react": '// alt text from a required CMS field written for it, '
                 'never the file name\n'
                 '<img src={photo.url} alt={photo.altText} />',
        "vue": '<!-- alt text from a required CMS field written for it, '
               'never the file name -->\n'
               '<img :src="photo.url" :alt="photo.altText">',
    },
    "bb-generic-link-text": {
        "why": "Link text such as \"Read more\" meets WCAG 2.4.4 when "
               "its sentence or paragraph says where it goes, but "
               "screen-reader users who list a page's links hear it "
               "without that context.",
        "fix": "Where you can, write link text that makes sense on its "
               "own (WCAG 2.4.9, level AAA), such as \"Read the 2026 "
               "pricing guide\", or add the missing words as visually "
               "hidden text inside the link.",
        "html_bad": '<p>Our 2026 pricing guide is out.\n'
                    '  <a href="/guide">Read more</a></p>',
        "html_good": '<p><a href="/guide">Read the 2026 pricing guide</a>'
                     '</p>',
        "react": '<a href={post.url}>\n  Read more<span '
                 'className="visually-hidden"> about {post.title}</span>\n'
                 '</a>',
        "vue": '<a :href="post.url">\n  Read more<span '
               'class="visually-hidden"> about {{ post.title }}</span>\n'
               '</a>',
    },
    # --------------------------------------------------------- rendered
    "bb-contrast-min": {
        "why": "Text with too little contrast against its background is "
               "hard or impossible to read for people with low vision or "
               "color deficiencies, and for anyone in bright light.",
        "fix": "Make text contrast at least 4.5:1 with its background "
               "(3:1 for large text: 24px, or 18.66px bold). Check light "
               "grays, text on images and text on brand colors.",
        "html_bad": '<p style="color: #999999; background: #ffffff">'
                    'Offer ends Friday</p>',
        "html_good": '<p style="color: #595959; background: #ffffff">'
                     'Offer ends Friday</p>',
        "react": '// styles.css: .note { color: #595959; } '
                 '/* 7:1 on white */\n'
                 '<p className="note">Offer ends Friday</p>',
        "vue": '<template>\n'
               '  <p class="note">Offer ends Friday</p>\n'
               '</template>\n'
               '\n'
               '<style scoped>\n'
               '.note { color: #595959; } /* 7:1 on white */\n'
               '</style>',
    },
    "bb-target-size": {
        "why": "Small targets packed close together are hard to hit for "
               "people with tremors or limited dexterity, and on touch "
               "screens.",
        "fix": "Make pointer targets at least 24 by 24 CSS pixels, or "
               "leave room around smaller ones so a 24-pixel circle on "
               "each does not touch its neighbors (WCAG 2.2's 2.5.8).",
        "html_bad": '<button type="button" aria-label="Previous"\n'
                    '  style="width: 16px; height: 16px; padding: 0">&lt;'
                    '</button>'
                    '<button type="button" aria-label="Next"\n'
                    '  style="width: 16px; height: 16px; padding: 0">&gt;'
                    '</button>',
        "html_good": '<button type="button" aria-label="Previous"\n'
                     '  style="min-width: 24px; min-height: 24px">&lt;'
                     '</button>'
                     '<button type="button" aria-label="Next"\n'
                     '  style="min-width: 24px; min-height: 24px">&gt;'
                     '</button>',
        "react": '// styles.css: .icon-button { min-width: 24px; '
                 'min-height: 24px; }\n'
                 '<button type="button" className="icon-button" '
                 'aria-label="Next" onClick={next}>\n'
                 '  <ChevronIcon aria-hidden="true" />\n</button>',
        "vue": '<template>\n'
               '  <button type="button" class="icon-button" aria-label="Next" @click="next">\n'
               '    <ChevronIcon aria-hidden="true" />\n'
               '  </button>\n'
               '</template>\n'
               '\n'
               '<style scoped>\n'
               '.icon-button { min-width: 24px; min-height: 24px; }\n'
               '</style>',
    },
    "bb-link-in-text": {
        "why": "A link told apart from the text around it only by its "
               "color cannot be found by people who cannot see the "
               "difference.",
        "fix": "Underline links in running text, or set them apart in "
               "another way than color (bold, a border). Color alone is "
               "enough when the link's color has at least 3:1 contrast "
               "with the text around it (W3C technique G183).",
        "html_bad": '<p style="color: #333333">Read our\n'
                    '  <a href="/terms" style="color: #1a5fb4; '
                    'text-decoration: none">terms of sale</a>\n'
                    '  before ordering.</p>',
        "html_good": '<p style="color: #333333">Read our\n'
                     '  <a href="/terms" style="color: #1a5fb4; '
                     'text-decoration: underline">terms of sale</a>\n'
                     '  before ordering.</p>',
        "react": '// styles.css: .prose a { text-decoration: underline; }\n'
                 '<p className="prose">Read our <a href="/terms">terms of '
                 'sale</a> before ordering.</p>',
        "vue": '<template>\n'
               '  <p class="prose">Read our <a href="/terms">terms of sale</a> before ordering.</p>\n'
               '</template>\n'
               '\n'
               '<style scoped>\n'
               '.prose a { text-decoration: underline; }\n'
               '</style>',
    },
    "bb-list": {
        "why": "Screen readers announce a list and how many items it "
               "holds. Other elements placed directly inside <ul> or <ol> "
               "break that.",
        "fix": "Put only <li> elements directly inside <ul> and <ol>; put "
               "any other content inside an <li>.",
        "html_bad": '<ul>\n  <div>Rye</div>\n  <li>Sourdough</li>\n</ul>',
        "html_good": '<ul>\n  <li>Rye</li>\n  <li>Sourdough</li>\n</ul>',
        "react": '<ul>\n  {loaves.map((loaf) => (\n'
                 '    <li key={loaf.id}><LoafCard loaf={loaf} /></li>\n'
                 '  ))}\n</ul>',
        "vue": '<ul>\n  <li v-for="loaf in loaves" :key="loaf.id">'
               '<LoafCard :loaf="loaf" /></li>\n</ul>',
    },
    "bb-listitem": {
        "why": "A list item outside a list is not announced as part of "
               "one, so users lose the count and the grouping.",
        "fix": "Put every <li> inside a <ul>, <ol> or <menu>.",
        "html_bad": '<div>\n  <li>Rye</li>\n  <li>Sourdough</li>\n</div>',
        "html_good": '<ul>\n  <li>Rye</li>\n  <li>Sourdough</li>\n</ul>',
        "react": '// LoafItem renders an <li>, so its parent must be a list\n'
                 '<ul>\n  {loaves.map((loaf) => <LoafItem key={loaf.id} '
                 'loaf={loaf} />)}\n</ul>',
        "vue": '<!-- LoafItem renders an <li>, so its parent must be a '
               'list -->\n<ul>\n  <LoafItem v-for="loaf in loaves" '
               ':key="loaf.id" :loaf="loaf" />\n</ul>',
    },
    "bb-definition-list": {
        "why": "Screen readers pair each term with its description "
               "reliably only when a <dl> holds <dt> and <dd> elements (or "
               "<div>s grouping them) and nothing else.",
        "fix": "Use <dt> for each term and <dd> for its description; "
               "group a pair in a <div> if you need a wrapper.",
        "html_bad": '<dl>\n  <p>Delivery</p>\n  <dd>Free over $50</dd>\n</dl>',
        "html_good": '<dl>\n  <dt>Delivery</dt>\n  <dd>Free over $50</dd>\n'
                     '</dl>',
        "react": '<dl>\n  {specs.map((s) => (\n    <div key={s.term}>'
                 '<dt>{s.term}</dt><dd>{s.value}</dd></div>\n  ))}\n</dl>',
        "vue": '<dl>\n  <div v-for="s in specs" :key="s.term">\n'
               '    <dt>{{ s.term }}</dt><dd>{{ s.value }}</dd>\n'
               '  </div>\n</dl>',
    },
    "bb-dlitem": {
        "why": "A term or description outside a <dl> is not announced as "
               "part of a list of terms.",
        "fix": "Put every <dt> and <dd> inside a <dl>, directly or in a "
               "<div> that groups a pair.",
        "html_bad": '<div>\n  <dt>Delivery</dt>\n  <dd>Free over $50</dd>\n'
                    '</div>',
        "html_good": '<dl>\n  <div>\n    <dt>Delivery</dt>\n'
                     '    <dd>Free over $50</dd>\n  </div>\n</dl>',
        "react": '<dl>\n  <div><dt>Delivery</dt><dd>Free over $50</dd>'
                 '</div>\n</dl>',
        "vue": '<dl>\n  <div><dt>Delivery</dt><dd>Free over $50</dd>'
               '</div>\n</dl>',
    },
    "bb-aria-required-children": {
        "why": "A role such as list, listbox, tablist or menu promises "
               "children of particular roles. When they are missing, "
               "assistive technology announces a broken structure: a list "
               "with no items, a tab list with no tabs.",
        "fix": "Give the children the roles their parent requires "
               "(listitem in a list, option in a listbox, tab in a "
               "tablist, menuitem in a menu), or use native elements, "
               "such as <ul> and <li>, which carry them already.",
        "html_bad": '<div role="list">\n  <span>Rye</span>\n'
                    '  <span>Sourdough</span>\n</div>',
        "html_good": '<div role="list">\n'
                     '  <div role="listitem">Rye</div>\n'
                     '  <div role="listitem">Sourdough</div>\n</div>',
        "react": '<div role="list">\n  {loaves.map((loaf) => (\n'
                 '    <div key={loaf.id} role="listitem">{loaf.name}</div>\n'
                 '  ))}\n</div>',
        "vue": '<div role="list">\n  <div v-for="loaf in loaves" '
               ':key="loaf.id" role="listitem">{{ loaf.name }}</div>\n'
               '</div>',
    },
    "bb-aria-required-parent": {
        "why": "A list item, tab, option or menu item outside the list, "
               "tab list, listbox or menu it belongs to is not announced "
               "as part of it, so users lose the grouping and the count.",
        "fix": "Put each such role inside the parent role it needs: "
               "listitem in list, tab in tablist, option in listbox, "
               "menuitem in menu or menubar.",
        "html_bad": '<div role="listitem">Rye</div>',
        "html_good": '<div role="list">\n  <div role="listitem">Rye</div>\n'
                     '</div>',
        "react": '<div role="list">\n'
                 '  <div role="listitem">{loaf.name}</div>\n</div>',
        "vue": '<div role="list">\n'
               '  <div role="listitem">{{ loaf.name }}</div>\n</div>',
    },
    "bb-aria-required-attr": {
        "why": "A role that needs a state but has none is announced "
               "with a default the page did not choose: Chromium reports "
               "a role=\"checkbox\" without aria-checked as not checked, "
               "whatever it shows.",
        "fix": "Prefer the native element (<input type=\"checkbox\">), "
               "which keeps its state for you. Otherwise give the role "
               "every state it requires, and keep it current.",
        "html_bad": '<div role="checkbox" tabindex="0">Gift wrap</div>',
        "html_good": '<label><input type="checkbox"> Gift wrap</label>',
        "react": '<label>\n  <input type="checkbox" checked={giftWrap}\n'
                 '    onChange={(e) => setGiftWrap(e.target.checked)} /> '
                 'Gift wrap\n</label>',
        "vue": '<label><input v-model="giftWrap" type="checkbox"> Gift wrap'
               '</label>',
    },
    "bb-aria-allowed-attr": {
        "why": "An ARIA attribute the element's role does not support is "
               "ignored or misread, so the state it was meant to give is "
               "lost.",
        "fix": "Use only attributes the role supports, such as "
               "aria-current=\"page\" on the link to the current page, or "
               "aria-pressed on a toggle button.",
        "html_bad": '<a href="/faq" aria-checked="true">FAQ</a>',
        "html_good": '<a href="/faq" aria-current="page">FAQ</a>',
        "react": '<a href="/faq" aria-current={isCurrent ? \'page\' : '
                 'undefined}>FAQ</a>',
        "vue": '<a href="/faq" :aria-current="isCurrent ? \'page\' : '
               'undefined">FAQ</a>',
    },
    "bb-aria-prohibited-attr": {
        "why": "aria-label on an element that cannot be named, such as a "
               "plain <div> or <span>, is ignored by many screen readers, "
               "so the label is never heard.",
        "fix": "Put the text in the element itself (visually hidden if "
               "need be), or give the element a role that can be named.",
        "html_bad": '<span class="badge" aria-label="3 items in cart">3'
                    '</span>',
        "html_good": '<span class="badge">3<span class="visually-hidden"> '
                     'items in cart</span></span>',
        "react": '<span className="badge">\n  {count}<span '
                 'className="visually-hidden"> items in cart</span>\n'
                 '</span>',
        "vue": '<span class="badge">\n  {{ count }}<span '
               'class="visually-hidden"> items in cart</span>\n</span>',
    },
    "bb-aria-conditional-attr": {
        "why": "WAI-ARIA allows some attributes only in some uses. On a "
               "native checkbox, browsers ignore aria-checked and report "
               "the box's real state, so a value that disagrees misleads "
               "only the people and tools that read the markup; row "
               "attributes outside a treegrid may be ignored or misread.",
        "fix": "Remove aria-checked from native checkboxes and let their "
               "checked state speak; use row attributes such as "
               "aria-expanded only where the row's role allows them.",
        "html_bad": '<label><input type="checkbox" aria-checked="true"> '
                    'Gift wrap</label>',
        "html_good": '<label><input type="checkbox" checked> Gift wrap'
                     '</label>',
        "react": '<label>\n  <input type="checkbox" checked={giftWrap}\n'
                 '    onChange={(e) => setGiftWrap(e.target.checked)} /> '
                 'Gift wrap\n</label>',
        "vue": '<label><input v-model="giftWrap" type="checkbox"> Gift wrap'
               '</label>',
    },
    "bb-aria-attr-value": {
        "why": "An ARIA attribute with a value its definition does not "
               "allow is ignored or misread.",
        "fix": "Use the values the attribute defines: true or false for "
               "states such as aria-expanded, ids that exist for "
               "references.",
        "html_bad": '<button type="button" aria-expanded="yes">Menu'
                    '</button>',
        "html_good": '<button type="button" aria-expanded="false">Menu'
                     '</button>',
        "react": '<button type="button" aria-expanded={open} '
                 'onClick={toggle}>Menu</button>',
        "vue": '<button type="button" :aria-expanded="open" '
               '@click="toggle">Menu</button>',
    },
    "bb-aria-deprecated-role": {
        "why": "A role WAI-ARIA has deprecated, such as directory, may "
               "not be supported by assistive technology, so the "
               "element's purpose is lost.",
        "fix": "Use the current equivalent (role=\"list\", or a native "
               "<ul>, instead of directory).",
        "html_bad": '<div role="directory">\n  <a href="/team/ana">Ana</a>\n'
                    '</div>',
        "html_good": '<ul>\n  <li><a href="/team/ana">Ana</a></li>\n</ul>',
        "react": '<ul>\n  {people.map((p) => <li key={p.id}>'
                 '<a href={p.url}>{p.name}</a></li>)}\n</ul>',
        "vue": '<ul>\n  <li v-for="p in people" :key="p.id">'
               '<a :href="p.url">{{ p.name }}</a></li>\n</ul>',
    },
    "bb-aria-braille": {
        "why": "WAI-ARIA lets a braille role description stand only "
               "beside a spoken one (aria-roledescription), and a braille "
               "label only on an element that has an accessible name, so "
               "braille and speech users are told the same thing; browsers "
               "ignore a braille role description that stands alone.",
        "fix": "Use aria-brailleroledescription only beside "
               "aria-roledescription, and aria-braillelabel only on an "
               "element that also has an accessible name. Most pages "
               "need neither.",
        "html_bad": '<button type="button" aria-brailleroledescription="tgl">'
                    'Mute</button>',
        "html_good": '<button type="button">Mute</button>',
        "react": '<button type="button" aria-pressed={muted} '
                 'onClick={toggleMute}>Mute</button>',
        "vue": '<button type="button" :aria-pressed="muted" '
               '@click="toggleMute">Mute</button>',
    },
    "bb-aria-hidden-body": {
        "why": "aria-hidden=\"true\" on <body> is an authoring error: "
               "current Chromium, Firefox and Safari ignore it there, as "
               "WAI-ARIA now tells browsers to, but an older browser may "
               "hide the entire page from screen readers.",
        "fix": "Remove aria-hidden from <body>. To keep users in a "
               "dialog, open a <dialog> with showModal(), or make the "
               "rest of the page inert; never hide <body> itself.",
        "where": "body-element",
        "html_bad": '<body aria-hidden="true">\n  <main><h1>Example</h1>'
                    '</main>\n</body>',
        "html_good": '<body>\n  <main><h1>Example</h1></main>\n</body>',
        "react": '// open dialogs with showModal(), which keeps users in '
                 'them\n'
                 'const dialogRef = useRef(null);\nreturn (\n  <>\n'
                 '    <button type="button" onClick={() => '
                 'dialogRef.current.showModal()}>Open</button>\n'
                 '    <dialog ref={dialogRef}>...</dialog>\n  </>\n);',
        "vue": '<!-- open dialogs with showModal(), which keeps users in '
               'them -->\n<dialog ref="dialog">...</dialog>\n'
               '<button type="button" @click="$refs.dialog.showModal()">'
               'Open</button>',
    },
    "bb-nested-interactive": {
        "why": "A control inside another (a link inside a button) cannot "
               "be reached or named by assistive technology: the outer "
               "control's role hides it.",
        "fix": "Place controls side by side, never inside one another. A "
               "clickable card should be one link, with any other "
               "controls outside it.",
        "html_bad": '<button type="button">Add to cart\n'
                    '  <a href="/help">Help</a>\n</button>',
        "html_good": '<button type="button">Add to cart</button>\n'
                     '<a href="/help">Help with ordering</a>',
        "react": '<>\n'
                 '  <button type="button" onClick={addToCart}>Add to cart</button>\n'
                 '  <a href="/help">Help with ordering</a>\n'
                 '</>',
        "vue": '<button type="button" @click="addToCart">Add to cart'
               '</button>\n<a href="/help">Help with ordering</a>',
    },
    "bb-scrollable-region": {
        "why": "Keyboard users can only scroll a region they can focus. A "
               "scrolling box with nothing focusable inside keeps its "
               "hidden content out of their reach in some browsers.",
        "fix": "Add tabindex=\"0\" to the scrolling element, with "
               "role=\"region\" and an aria-label saying what it holds.",
        "html_bad": '<div style="height: 60px; overflow: auto">\n'
                    '  <p>Line one</p><p>Line two</p><p>Line three</p>'
                    '<p>Line four</p>\n</div>',
        "html_good": '<div style="height: 60px; overflow: auto" '
                     'tabindex="0"\n'
                     '  role="region" aria-label="Order notes">\n'
                     '  <p>Line one</p><p>Line two</p><p>Line three</p>'
                     '<p>Line four</p>\n</div>',
        "react": '<div className="notes" tabIndex={0} role="region" '
                 'aria-label="Order notes">\n  {notes}\n</div>',
        "vue": '<div class="notes" tabindex="0" role="region" '
               'aria-label="Order notes">\n  {{ notes }}\n</div>',
    },
    "bb-server-image-map": {
        "why": "A server-side image map can be used only by clicking "
               "points on the image, which keyboard and screen-reader "
               "users cannot do.",
        "fix": "Replace it with ordinary links, or a client-side <map> "
               "whose <area> elements have alt text.",
        "html_bad": '<a href="/floors"><img src="floors.png" '
                    'alt="Store floors" ismap></a>',
        "html_good": '<ul>\n  <li><a href="/floors/1">First floor</a></li>\n'
                     '  <li><a href="/floors/2">Second floor</a></li>\n'
                     '</ul>',
        "react": '<ul>\n  {floors.map((f) => <li key={f.id}>'
                 '<a href={f.url}>{f.name}</a></li>)}\n</ul>',
        "vue": '<ul>\n  <li v-for="f in floors" :key="f.id">'
               '<a :href="f.url">{{ f.name }}</a></li>\n</ul>',
    },
    "bb-summary-name": {
        "why": "A <summary> is the button that opens its details. Without "
               "text, users hear a button with no name.",
        "fix": "Put text in every <summary> that says what it reveals.",
        "html_bad": '<details>\n  <summary></summary>\n'
                    '  <p>Returns are free within 30 days.</p>\n</details>',
        "html_good": '<details>\n  <summary>Return policy</summary>\n'
                     '  <p>Returns are free within 30 days.</p>\n'
                     '</details>',
        "react": '<details>\n  <summary>{faq.question}</summary>\n'
                 '  <p>{faq.answer}</p>\n</details>',
        "vue": '<details>\n  <summary>{{ faq.question }}</summary>\n'
               '  <p>{{ faq.answer }}</p>\n</details>',
    },
    "bb-object-alt": {
        "why": "Screen readers cannot describe an embedded image, chart "
               "or media <object> that has no text alternative.",
        "fix": "Give each <object> an aria-label (or title) that says "
               "what it shows, or embed an image with <img> and alt "
               "text instead.",
        "html_bad": '<object data="sales.svg" type="image/svg+xml"></object>',
        "html_good": '<object data="sales.svg" type="image/svg+xml"\n'
                     '  aria-label="Sales by month, highest in December">'
                     '</object>',
        "react": '<img src={salesChart} alt="Sales by month, highest in '
                 'December" />',
        "vue": '<img :src="salesChart" alt="Sales by month, highest in '
               'December">',
    },
    "bb-element-lang": {
        "why": "Screen readers switch voice and pronunciation for a "
               "passage in another language only when its lang names a "
               "valid language.",
        "fix": "Mark a passage in another language with lang and a valid "
               "tag: \"fr\", \"es-MX\", \"zh-Hant\".",
        "html_bad": '<p lang="francais">Bonjour et bienvenue.</p>',
        "html_good": '<p lang="fr">Bonjour et bienvenue.</p>',
        "react": '<p lang="fr">Bonjour et bienvenue.</p>',
        "vue": '<p lang="fr">Bonjour et bienvenue.</p>',
    },
    "bb-xml-lang-mismatch": {
        "why": "When lang and xml:lang name different languages, tools "
               "that read one or the other can pick the wrong one.",
        "fix": "In an HTML page, set lang alone. If you keep xml:lang "
               "(XHTML), give it the same value as lang.",
        "where": "html",
        "html_bad": '<html lang="en" xml:lang="fr">',
        "html_good": '<html lang="en">',
        "react": '// app/layout.jsx (Next.js): lang alone, no xml:lang\n'
                 'export default function RootLayout({ children }) {\n'
                 '  return (\n'
                 '    <html lang="en">\n'
                 '      <body>{children}</body>\n'
                 '    </html>\n'
                 '  );\n'
                 '}',
        "vue": '<!-- index.html -->\n<html lang="en">',
    },
    "bb-td-headers": {
        "why": "A screen reader reads a cell's headers from its headers "
               "attribute. Ids of cells in another table, or of the cell "
               "itself, give users no headers or the wrong ones.",
        "fix": "Point headers only at <th> ids in the same table, or "
               "drop headers and use <th scope> for simple tables.",
        "html_bad": '<table>\n  <tr><th id="h-plan">Plan</th>'
                    '<th id="h-price">Price</th></tr>\n'
                    '  <tr><td id="c-basic" headers="c-basic">Basic</td>'
                    '<td headers="h-price">$10</td></tr>\n</table>',
        "html_good": '<table>\n  <tr><th scope="col">Plan</th>'
                     '<th scope="col">Price</th></tr>\n'
                     '  <tr><td>Basic</td><td>$10</td></tr>\n</table>',
        "react": '<table>\n  <thead><tr><th scope="col">Plan</th>'
                 '<th scope="col">Price</th></tr></thead>\n'
                 '  <tbody>{plans.map((p) => (\n'
                 '    <tr key={p.id}><td>{p.name}</td><td>{p.price}</td>'
                 '</tr>\n  ))}</tbody>\n</table>',
        "vue": '<table>\n  <thead><tr><th scope="col">Plan</th>'
               '<th scope="col">Price</th></tr></thead>\n'
               '  <tbody><tr v-for="p in plans" :key="p.id">'
               '<td>{{ p.name }}</td><td>{{ p.price }}</td></tr></tbody>\n'
               '</table>',
    },
    "bb-th-data-cells": {
        "why": "A header cell that heads no data cell is announced for "
               "nothing, or misleads users about the table's columns.",
        "fix": "Make sure every <th> heads at least one cell: fill the "
               "column or remove the header.",
        "html_bad": '<table>\n  <tr><th>Plan</th><th>Price</th>'
                    '<th>Notes</th></tr>\n'
                    '  <tr><td>Basic</td><td>$10</td></tr>\n</table>',
        "html_good": '<table>\n  <tr><th>Plan</th><th>Price</th></tr>\n'
                     '  <tr><td>Basic</td><td>$10</td></tr>\n</table>',
        "react": '// only the columns that have data: their headers and '
                 'their cells alike\n'
                 'const shown = columns.filter((c) => rows.some((r) => '
                 'r[c.id] != null));\nreturn (\n'
                 '  <table>\n'
                 '    <thead>\n'
                 '      <tr>{shown.map((c) => <th key={c.id} scope="col">'
                 '{c.label}</th>)}</tr>\n'
                 '    </thead>\n'
                 '    <tbody>\n'
                 '      {rows.map((r) => (\n'
                 '        <tr key={r.id}>{shown.map((c) => <td key={c.id}>'
                 '{r[c.id]}</td>)}</tr>\n'
                 '      ))}\n'
                 '    </tbody>\n'
                 '  </table>\n);',
        "vue": '<script setup>\nimport { computed } from \'vue\'\n'
               'const props = defineProps([\'columns\', \'rows\'])\n'
               '// only the columns that have data: their headers and their '
               'cells alike\n'
               'const shown = computed(() => props.columns.filter((c) =>\n'
               '  props.rows.some((r) => r[c.id] != null)))\n</script>\n'
               '<template>\n'
               '  <table>\n'
               '    <thead>\n'
               '      <tr><th v-for="c in shown" :key="c.id" scope="col">'
               '{{ c.label }}</th></tr>\n'
               '    </thead>\n'
               '    <tbody>\n'
               '      <tr v-for="r in rows" :key="r.id">\n'
               '        <td v-for="c in shown" :key="c.id">{{ r[c.id] }}'
               '</td>\n'
               '      </tr>\n'
               '    </tbody>\n'
               '  </table>\n'
               '</template>',
    },
    "bb-frame-title-unique": {
        "why": "Two frames with the same title sound the same to "
               "screen-reader users; if they hold different things, "
               "users cannot tell which is which.",
        "fix": "Give each frame a title that says what it holds, unique "
               "unless the frames serve the same purpose.",
        "html_bad": '<iframe src="/widgets/hours.html" title="Widget">'
                    '</iframe>\n'
                    '<iframe src="/widgets/map.html" title="Widget"></iframe>',
        "html_good": '<iframe src="/widgets/hours.html" title="Opening hours">'
                     '</iframe>\n'
                     '<iframe src="/widgets/map.html" title="Map of our '
                     'store"></iframe>',
        "react": '<>\n'
                 '  <iframe src={hoursUrl} title="Opening hours" />\n'
                 '  <iframe src={mapUrl} title="Map of our store" />\n'
                 '</>',
        "vue": '<iframe :src="hoursUrl" title="Opening hours"></iframe>\n'
               '<iframe :src="mapUrl" title="Map of our store"></iframe>',
    },
    "bb-multiple-labels": {
        "why": "Screen readers read a field with two <label> elements "
               "inconsistently: some read one, some both.",
        "fix": "Give each field one <label>. Put extra hints in text "
               "tied to the field with aria-describedby.",
        "html_bad": '<label for="zip">ZIP</label>\n'
                    '<label for="zip">Postal code</label>\n'
                    '<input id="zip" autocomplete="postal-code">',
        "html_good": '<label for="zip">ZIP code</label>\n'
                     '<input id="zip" autocomplete="postal-code" '
                     'aria-describedby="zip-hint">\n'
                     '<p id="zip-hint">Five digits, such as 11354.</p>',
        "react": '<>\n'
                 '  <label htmlFor="zip">ZIP code</label>\n'
                 '  <input id="zip" autoComplete="postal-code" aria-describedby="zip-hint" />\n'
                 '  <p id="zip-hint">Five digits, such as 11354.</p>\n'
                 '</>',
        "vue": '<label for="zip">ZIP code</label>\n'
               '<input id="zip" v-model="zip" autocomplete="postal-code" '
               'aria-describedby="zip-hint">\n'
               '<p id="zip-hint">Five digits, such as 11354.</p>',
    },
    "bb-inline-spacing": {
        "why": "People with dyslexia or low vision widen letter, word "
               "and line spacing with their own styles; !important in a "
               "style attribute stops them.",
        "fix": "Do not set letter-spacing, word-spacing or line-height "
               "with !important in style attributes; set them in your "
               "stylesheet.",
        "html_bad": '<p style="letter-spacing: 0.02em !important">Terms and '
                    'conditions apply.</p>',
        "html_good": '<p class="small-print">Terms and conditions apply.'
                     '</p>',
        "react": '// styles.css: .small-print { line-height: 1.5; }\n'
                 '<p className="small-print">Terms and conditions apply.'
                 '</p>',
        "vue": '<template>\n'
               '  <p class="small-print">Terms and conditions apply.</p>\n'
               '</template>\n'
               '\n'
               '<style scoped>\n'
               '.small-print { line-height: 1.5; }\n'
               '</style>',
    },
    "bb-reflow-320": {
        "why": "Someone who zooms to 400% sees the page about 320 CSS "
               "pixels wide. Content that does not reflow makes them "
               "scroll sideways to read every line.",
        "fix": "Use flexible widths (max-width: 100%, flex or grid that "
               "wraps) instead of fixed pixel widths, and let long words "
               "break (overflow-wrap: anywhere).",
        "html_bad": '<div style="width: 1000px">\n  Order before noon for '
                    'delivery the same day across the whole city.\n</div>',
        "html_good": '<div style="max-width: 1000px">\n  Order before noon '
                     'for delivery the same day across the whole city.\n'
                     '</div>',
        "react": '// styles.css: .banner { max-width: 1000px; }\n'
                 '<div className="banner">Order before noon for delivery '
                 'the same day.</div>',
        "vue": '<template>\n'
               '  <div class="banner">Order before noon for delivery the same day.</div>\n'
               '</template>\n'
               '\n'
               '<style scoped>\n'
               '.banner { max-width: 1000px; }\n'
               '</style>',
    },
}


def guidance_for(rule_id: str) -> dict:
    """The guidance for a rule, or {} for one that has none."""
    return GUIDANCE.get(rule_id) or {}


def load_guidance() -> dict:
    """The guidance in the shape reports read: {"rules": {id: {...}}}."""
    return {"rules": GUIDANCE}
