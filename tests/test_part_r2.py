"""Part R, stage 2: the linter reads each framework's click handlers and
class builders (P3-10), a click handler on a wrapper around links is a
warning (N26), and a scan skips build output and what git ignores (P3-10).

P2-14, the rulebook's citations checked against W3C's sources, is in
tests/test_citations.py; the rule fixes the two reviews of the citations
asked for (R2B, R2E) are here, at the end.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bellbriar_harness import lint as L                          # noqa: E402
from bellbriar_harness.lint import ERROR, WARN, collect, lint_text  # noqa: E402

GIT = shutil.which("git")


def severities(src: str, path: str, rule: str) -> list:
    return [f.severity for f in lint_text(src, path) if f.rule_id == rule]


def findings(src: str, path: str, rule: str) -> list:
    return [f for f in lint_text(src, path) if f.rule_id == rule]


class TestFrameworkClickHandlers(unittest.TestCase):
    """P3-10: a Vue repo with div click handlers linted clean."""

    def test_each_spelling_is_a_click_handler(self):
        for path, src in (
                ("C.vue", '<template><div @click="go">x</div></template>'),
                ("C.vue", '<template><div v-on:click="go()">x</div></template>'),
                ("C.vue", '<template><div @click.prevent="go">x</div></template>'),
                ("C.vue", '<template><span @click="go">x</span></template>'),
                ("C.vue", '<template><div @click.stop="go">x</div></template>'),
                ("a.html", '<div x-on:click="open = !open">x</div>'),
                ("a.html", '<div @click="open = true">x</div>'),
                ("C.svelte", '<div on:click={go}>x</div>'),
                ("C.svelte", '<div on:click|preventDefault={go}>x</div>'),
                ("x.component.html", '<div (click)="go()">x</div>'),
                ("el.ts", 'html`<div @click=${this.go}>x</div>`'),
                ("C.jsx", '<div onClick={go}>x</div>'),
                ("C.svelte", '<div onclick={go}>x</div>')):
            with self.subTest(path=path, src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [ERROR])

    def test_a_handler_that_only_stops_the_event_is_a_warning(self):
        for path, src in (
                ("C.vue", '<template><div @click.stop>x</div></template>'),
                ("C.vue", '<template><div @click.stop.prevent>x</div></template>'),
                ("C.svelte", '<div on:click|stopPropagation>x</div>'),
                ("x.component.html",
                 '<div (click)="$event.stopPropagation()">x</div>'),
                ("C.vue", '<template><div @click="$event.stopPropagation()">'
                          'x</div></template>'),
                ("C.vue", '<template><div @click="(e) => e.stopPropagation()">'
                          'x</div></template>')):
            with self.subTest(path=path, src=src):
                got = findings(src, path, "bl-div-click")
                self.assertEqual([f.severity for f in got], [WARN])
                self.assertIn("only stops the event", got[0].message)

    def test_the_self_modifier_is_the_backdrop_pattern(self):
        for path, src in (
                ("C.vue", '<template><div class="backdrop" @click.self='
                          '"close">x</div></template>'),
                ("C.svelte", '<div on:click|self={close}>x</div>')):
            with self.subTest(path=path):
                got = findings(src, path, "bl-div-click")
                self.assertEqual([f.severity for f in got], [WARN])
                self.assertIn("self modifier", got[0].message)

    def test_anchors_and_down_events_read_the_same_spellings(self):
        for path, src in (
                ("C.vue", '<template><a @click="go">x</a></template>'),
                ("x.component.html", '<a href="#" (click)="go()">x</a>'),
                ("C.svelte", '<a on:click={go}>x</a>'),
                ("a.html", '<a x-on:click="go()">x</a>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-anchor-button"),
                                 [ERROR])
        for path, src in (
                ("C.vue", '<template><button type="button" @mousedown="go">'
                          'x</button></template>'),
                ("C.svelte", '<a href="/x" on:pointerdown={go}>x</a>'),
                ("x.component.html", '<button type="button" '
                                     '(pointerdown)="go()">x</button>')):
            with self.subTest(src=src):
                self.assertEqual(
                    severities(src, path, "bl-downevent-activation"), [WARN])

    def test_lookalikes_are_not_click_handlers(self):
        for path, src in (
                ("C.vue", '<template><div :click="x">x</div></template>'),
                ("C.vue", '<template><div @click-outside="close">x</div>'
                          '</template>'),
                ("C.vue", '<template><div @clickaway="close">x</div></template>'),
                ("x.component.html", '<div (clickOutside)="close()">x</div>'),
                ("C.jsx", '<div onClickOutside={close}>x</div>'),
                ("C.jsx", '<div data-onclick="x">x</div>'),
                ("C.svelte", '<div use:clickOutside={close}>x</div>'),
                ("C.vue", '<template><div title="@click here">x</div>'
                          '</template>')):
            with self.subTest(src=src):
                self.assertEqual(findings(src, path, "bl-div-click"), [])


class TestClassBuilders(unittest.TestCase):
    """P3-10: classes built by cn() or clsx(), or bound, were not read."""

    def check(self, cases):
        for path, src, expected in cases:
            with self.subTest(path=path, src=src):
                self.assertEqual(
                    severities(src, path, "bl-outline-none-class"), expected)

    def test_class_builders_and_template_literals(self):
        b = '<button type="button" className={%s}>x</button>'
        self.check((
            ("C.tsx", b % 'cn("outline-none")', [ERROR]),
            ("C.tsx", b % 'cn("outline-none", "focus-visible:ring-2")', []),
            # A replacement on a condition, the removal always: a warning.
            ("C.tsx", b % 'clsx("outline-none", { "focus-visible:ring-2": ok })',
             [WARN]),
            ("C.tsx", b % 'classnames("outline-none")', [ERROR]),
            ("C.tsx", b % 'cx("outline-none")', [ERROR]),
            ("C.tsx", b % 'twMerge("outline-none", className)', [WARN]),
            ("C.tsx", b % 'cn(buttonVariants({ variant }), "outline-none")',
             [WARN]),
            ("C.tsx", b % 'cn("outline-none", flat && "focus-visible:ring-2")',
             [WARN]),
            ("C.tsx", b % 'cn(flat && "outline-none", flat && "focus-visible:'
             'ring-2")', []),
            ("C.tsx", b % 'cn(flat && "outline-none")', [WARN]),
            ("C.tsx", b % '`outline-none`', [ERROR]),
            ("C.tsx", b % '`${base} outline-none`', [WARN]),
            ("C.tsx", b % '`outline-none ${on ? "ring-2" : ""}`', [ERROR]),
            ("C.tsx", b % '"outline-none focus-visible:ring-2"', []),
            ("C.tsx", b % 'styles.plain', []),
        ))

    def test_values_and_conditions_in_an_expression(self):
        """An identifier where a class goes makes the reading partial; one
        that is only a condition, or an object's value, does not."""
        b = '<button type="button" className={%s}>x</button>'
        self.check((
            ("C.tsx", b % '"outline-none " + extra', [WARN]),
            ("C.tsx", b % 'extra + " outline-none"', [WARN]),
            ("C.tsx", b % '"outline-none " + (on ? ring : "")', [WARN]),
            ("C.tsx", b % 'cn("outline-none", on ? "bg-red" : base)', [WARN]),
            ("C.tsx", b % 'cn("outline-none", on && ring)', [WARN]),
            ("C.tsx", b % 'cn("outline-none", ring ?? "")', [WARN]),
            ("C.tsx", b % 'cn("outline-none", { [ring]: on })', [WARN]),
            ("C.tsx", b % 'cn("outline-none", `${size} x`)', [WARN]),
            ("C.tsx", b % 'cn("outline-none", { "bg-red": isError })', [ERROR]),
            ("C.tsx", b % 'cn("outline-none", { active: isActive })', [ERROR]),
            ("C.tsx", b % 'cn("outline-none", !flat && "x")', [ERROR]),
            ("C.tsx", b % 'cn("outline-none", /* focus-visible:ring-2 */ "x")',
             [ERROR]),
            ("C.tsx", b % 'cn("outline-none", on ? "" : "focus:ring-2")',
             [WARN]),
            ("C.tsx", b % '"outline-none" + " " + "focus-visible:ring-2"', []),
            # A template literal inside a template literal.
            ("C.tsx", b % '`outline-none ${on ? `focus-visible:ring-2` : ""}`',
             [WARN]),
            ("C.tsx", b % '`outline-none ${on ? `ring-2` : ""}`', [ERROR]),
        ))

    def test_bound_classes(self):
        self.check((
            ("C.vue", '<template><button type="button" :class="[\'outline-none'
                      '\', \'focus-visible:ring-2\']">x</button></template>', []),
            ("C.vue", '<template><button type="button" :class="{ \'outline-none'
                      '\': flat }">x</button></template>', [WARN]),
            ("C.vue", '<template><button type="button" class="outline-none" '
                      ':class="{ \'focus-visible:ring-2\': ok }">x</button>'
                      '</template>', [WARN]),
            ("C.vue", '<template><button type="button" v-bind:class="[\'outline'
                      '-none\', extra]">x</button></template>', [WARN]),
            ("C.svelte", '<button type="button" class:outline-none={flat}>x'
                         '</button>', [WARN]),
            ("C.svelte", '<button type="button" class="btn {on ? \'outline-none'
                         '\' : \'\'}">x</button>', [WARN]),
            ("C.svelte", '<button type="button" class="outline-none {extra}">x'
                         '</button>', [WARN]),
            ("x.component.html", '<button type="button" [ngClass]="'
                                 '{\'outline-none\': flat}">x</button>', [WARN]),
            ("x.component.html", '<button type="button" [class.outline-none]='
                                 '"flat">x</button>', [WARN]),
            ("x.component.html", '<button type="button" [class]="\'outline-none'
                                 '\'">x</button>', [ERROR]),
            ("a.html", '<button type="button" class="outline-none">x</button>',
             [ERROR]),
        ))

    def test_the_finding_names_the_class_attribute_line(self):
        src = ('<button\n  type="button"\n  className={cn(\n'
               '    "outline-none"\n  )}\n>x</button>')
        got = findings(src, "C.tsx", "bl-outline-none-class")
        self.assertEqual([(f.severity, f.line) for f in got], [(ERROR, 3)])

    def test_a_partial_reading_says_why_it_is_a_warning(self):
        got = findings('<button type="button" className={cn("outline-none", '
                       'className)}>x</button>', "C.tsx",
                       "bl-outline-none-class")
        self.assertIn("an expression it cannot read", got[0].message)
        got = findings('<button type="button" className={cn(flat && '
                       '"outline-none")}>x</button>', "C.tsx",
                       "bl-outline-none-class")
        self.assertIn("only on a condition", got[0].message)


class TestWrapperDivs(unittest.TestCase):
    """N26: a wrapper div whose click handler only receives clicks from the
    links inside it (a dropdown that closes on selection) was an ERROR."""

    def test_a_div_around_focusable_elements_is_a_warning(self):
        for path, src in (
                ("C.tsx", '<div onClick={close}><a href="/a">A</a>'
                          '<a href="/b">B</a></div>'),
                ("C.tsx", '<div onClick={close}><Link href="/a">A</Link></div>'),
                ("C.tsx", '<div onClick={focus}><input type="text" /></div>'),
                ("C.tsx", '<div onClick={close}><div tabIndex={0}>x</div></div>'),
                ("C.tsx", '<div onClick={close}><span><button type="button">'
                          'x</button></span></div>'),
                ("C.vue", '<template><div @click="close"><router-link to="/a">'
                          'A</router-link></div></template>'),
                ("x.component.html", '<div (click)="close()"><a routerLink="/a">'
                                     'A</a></div>')):
            with self.subTest(src=src):
                got = findings(src, path, "bl-div-click")
                self.assertEqual([f.severity for f in got], [WARN])
                self.assertIn("around links, buttons or fields", got[0].message)

    def test_a_div_around_nothing_focusable_is_still_an_error(self):
        for src in ('<div onClick={toggle}><span>Menu</span><ChevronDownIcon />'
                    '</div>',
                    '<div onClick={go}><a>no href</a></div>',
                    '<div onClick={go}><input type="hidden" name="x" /></div>',
                    '<div onClick={go}><div tabIndex={-1}>x</div></div>',
                    '<div onClick={go}><p contentEditable="false">x</p></div>',
                    '<div onClick={go}>x</div><a href="/">after</a>',
                    '<div onClick={go} />'):
            with self.subTest(src=src):
                self.assertEqual(severities(src, "C.tsx", "bl-div-click"),
                                 [ERROR])


class TestComponentsAreFollowed(unittest.TestCase):
    """N26 on vercel/commerce: the dropdown's links are rendered by a
    component in another file, <FilterItem>, through two more components:
    the last renders <DynamicTag href=…>, next/link's Link or a <p>."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, rel: str, text: str) -> Path:
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def lint(self, p: Path) -> list:
        return severities(p.read_text(encoding="utf-8"), str(p), "bl-div-click")

    WRAPPER = ('import { FilterItem } from "%s";\n'
               'export default function Dropdown({ list }) {\n'
               '  return (\n'
               '    <div onClick={() => setOpen(false)}>\n'
               '      {list.map((item) => <FilterItem key={item.path} '
               'item={item} />)}\n'
               '    </div>\n'
               '  );\n'
               '}\n')

    def test_the_commerce_dropdown(self):
        self.write("filter/item.tsx",
                   'import Link from "next/link";\n'
                   'function PathFilterItem({ item }) {\n'
                   '  const DynamicTag = item.active ? "p" : Link;\n'
                   '  return <li><DynamicTag href={item.path}>{item.title}'
                   '</DynamicTag></li>;\n'
                   '}\n'
                   'function SortFilterItem({ item }) {\n'
                   '  return <li><p>{item.title}</p></li>;\n'
                   '}\n'
                   'export function FilterItem({ item }) {\n'
                   '  return "path" in item ? <PathFilterItem item={item} /> '
                   ': <SortFilterItem item={item} />;\n'
                   '}\n')
        p = self.write("filter/dropdown.tsx", self.WRAPPER % "./item")
        self.assertEqual(self.lint(p), [WARN])

    def test_a_component_that_renders_nothing_focusable(self):
        self.write("filter/item.tsx", 'export function FilterItem({ item }) {\n'
                   '  return <li><p>{item.title}</p></li>;\n}\n')
        p = self.write("filter/dropdown.tsx", self.WRAPPER % "./item")
        self.assertEqual(self.lint(p), [ERROR])

    def test_only_the_imported_component_counts(self):
        """Another component in the same module renders a button; the one
        the wrapper uses does not."""
        self.write("filter/item.tsx",
                   'export function Toolbar() {\n'
                   '  return <button type="button">x</button>;\n}\n'
                   'export function FilterItem({ item }) {\n'
                   '  return <li><p>{item.title}</p></li>;\n}\n')
        p = self.write("filter/dropdown.tsx", self.WRAPPER % "./item")
        self.assertEqual(self.lint(p), [ERROR])

    def test_a_component_defined_in_the_same_file(self):
        for body, expected in (('<button type="button">x</button>', WARN),
                               ('<span>x</span>', ERROR)):
            with self.subTest(body=body):
                p = self.write("Menu.tsx",
                               'const Row = () => %s;\n'
                               'export function Menu() {\n'
                               '  return <div onClick={close}><Row /></div>;\n'
                               '}\n' % body)
                self.assertEqual(self.lint(p), [expected])

    def test_a_tsconfig_path_alias(self):
        self.write("tsconfig.json",
                   '{\n  // shadcn/ui and Next.js\n  "compilerOptions": {\n'
                   '    "paths": { "@/*": ["./src/*"] }, /* trailing */\n'
                   '  },\n}\n')
        self.write("src/components/nav-item.tsx",
                   'export const NavItem = ({ href }) => <a href={href}>x</a>;\n')
        p = self.write("src/app/menu.tsx",
                       'import { NavItem } from "@/components/nav-item";\n'
                       'export function Menu() {\n'
                       '  return <div onClick={close}><NavItem href="/" />'
                       '</div>;\n}\n')
        self.assertEqual(self.lint(p), [WARN])
        # A relative path from a folder below the tsconfig.
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        os.chdir(self.tmp / "src")
        self.assertEqual(severities(p.read_text(encoding="utf-8"),
                                    "app/menu.tsx", "bl-div-click"), [WARN])

    def test_a_component_from_a_package_is_not_followed(self):
        p = self.write("menu.tsx",
                       'import { Card } from "@acme/ui";\n'
                       'export function Menu() {\n'
                       '  return <div onClick={open}><Card /></div>;\n}\n')
        self.assertEqual(self.lint(p), [ERROR])

    def test_vue_single_file_components(self):
        self.write("Item.vue", '<template><a href="/x">x</a></template>\n')
        self.write("ItemRow.vue", '<template><li><a href="/y">y</a></li>'
                                  '</template>\n')
        for tag in ('<Item v-for="i in items" :key="i" />',
                    '<item-row v-for="i in items" :key="i" />'):
            with self.subTest(tag=tag):
                p = self.write("Menu.vue",
                               '<script setup>\nimport Item from "./Item.vue";\n'
                               'import ItemRow from "./ItemRow.vue";\n</script>\n'
                               '<template><div @click="close">%s</div>'
                               '</template>\n' % tag)
                self.assertEqual(self.lint(p), [WARN])

    def test_an_import_cycle_ends(self):
        self.write("a.tsx", 'import { B } from "./b";\n'
                            'export function A() { return <B />; }\n')
        self.write("b.tsx", 'import { A } from "./a";\n'
                            'export function B() { return <A />; }\n')
        p = self.write("menu.tsx", 'import { A } from "./a";\n'
                       'export function Menu() {\n'
                       '  return <div onClick={go}><A /></div>;\n}\n')
        self.assertEqual(self.lint(p), [ERROR])

    def test_an_edited_component_is_read_again(self):
        item = self.write("item.tsx", 'export const Item = () => <p>x</p>;\n')
        p = self.write("menu.tsx", 'import { Item } from "./item";\n'
                       'export const Menu = () => <div onClick={go}><Item />'
                       '</div>;\n')
        self.assertEqual(self.lint(p), [ERROR])
        item.write_text('export const Item = () => <a href="/x">xx</a>;\n',
                        encoding="utf-8")
        self.assertEqual(self.lint(p), [WARN])


class TestTheScan(unittest.TestCase):
    """P3-10: the scan entered build folders. It now skips the common
    tools' build output and caches, and whatever git ignores."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def files(self, *rels):
        for rel in rels:
            p = self.tmp / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("<div>x</div>\n", encoding="utf-8")

    def scan(self, rel="."):
        root = self.tmp / rel
        return sorted(p.relative_to(root).as_posix() for p in collect([str(root)]))

    def git(self, *args, cwd=None):
        subprocess.run(["git", "-C", str(cwd or self.tmp), *args], check=True,
                       capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t",
                            "GIT_AUTHOR_EMAIL": "t@example.com",
                            "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@example.com"})

    def test_build_folders_of_the_common_tools_are_skipped(self):
        self.files("src/App.tsx", ".svelte-kit/generated/root.js",
                   ".output/public/index.html", "storybook-static/main.js",
                   ".vercel/output/static/x.html", ".astro/types.d.ts",
                   ".angular/cache/x.js", "_site/index.html",
                   ".docusaurus/client.js", "bower_components/x/x.js")
        self.assertEqual(self.scan(), ["src/App.tsx"])

    def test_a_folder_named_on_the_command_line_is_scanned(self):
        self.files(".svelte-kit/generated/root.js")
        self.assertEqual(self.scan(".svelte-kit"), ["generated/root.js"])

    @unittest.skipUnless(GIT, "needs git")
    def test_what_git_ignores_is_skipped(self):
        self.git("init", "-q")
        (self.tmp / ".gitignore").write_text("generated/\n*.gen.tsx\n")
        self.files("src/App.tsx", "src/x.gen.tsx", "generated/y.tsx",
                   "src/kept.gen.tsx")
        self.git("add", "-f", "src/kept.gen.tsx", "src/App.tsx", ".gitignore")
        self.git("commit", "-qm", "init")
        self.files("src/New.tsx")      # new, not yet committed: linted
        self.assertEqual(self.scan(), ["src/App.tsx", "src/New.tsx",
                                       "src/kept.gen.tsx"])
        self.assertEqual(self.scan("src"), ["App.tsx", "New.tsx",
                                            "kept.gen.tsx"])

    @unittest.skipUnless(GIT, "needs git")
    def test_an_ignored_folder_or_file_named_on_the_command_line_is_linted(self):
        self.git("init", "-q")
        (self.tmp / ".gitignore").write_text("generated/\n")
        self.files("generated/y.tsx", "generated/deep/z.tsx",
                   "generated/tracked.tsx")
        # A tracked file in it: git then lists the others one by one.
        self.git("add", "-f", "generated/tracked.tsx")
        self.git("commit", "-qm", "init")
        self.assertEqual(self.scan("generated"),
                         ["deep/z.tsx", "tracked.tsx", "y.tsx"])
        self.assertEqual(self.scan("generated/deep"), ["z.tsx"])
        one = self.tmp / "generated" / "y.tsx"
        self.assertEqual(collect([str(one)]), [one])

    @unittest.skipUnless(GIT, "needs git")
    def test_a_nested_repository_reads_its_own_ignore_rules(self):
        self.git("init", "-q")
        (self.tmp / ".gitignore").write_text("*.gen.tsx\n")
        self.files("app/App.tsx", "theme/src/a.tsx", "theme/out-x/b.tsx",
                   "theme/src/c.gen.tsx")
        self.git("init", "-q", cwd=self.tmp / "theme")
        (self.tmp / "theme" / ".gitignore").write_text("out-x/\n")
        self.assertEqual(self.scan(), ["app/App.tsx", "theme/src/a.tsx",
                                       "theme/src/c.gen.tsx"])

    @unittest.skipUnless(GIT, "needs git")
    def test_a_hooks_git_variables_do_not_redirect_the_lookup(self):
        """Inside a git hook GIT_DIR names the hook's repository."""
        other = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, True)
        self.git("init", "-q", cwd=other)
        self.git("init", "-q")
        (self.tmp / ".gitignore").write_text("generated/\n")
        self.files("src/App.tsx", "generated/y.tsx")
        with mock.patch.dict(os.environ, {"GIT_DIR": str(other / ".git"),
                                          "GIT_WORK_TREE": str(other)}):
            self.assertEqual(self.scan(), ["src/App.tsx"])

    @unittest.skipUnless(GIT and os.name == "posix", "needs git and sh")
    def test_a_repositorys_fsmonitor_command_is_not_run(self):
        """git ls-files starts the command a repository's core.fsmonitor
        names; the lookup turns it off."""
        self.git("init", "-q")
        marker = self.tmp.parent / (self.tmp.name + "-ran")
        self.addCleanup(lambda: marker.unlink() if marker.exists() else None)
        hook = self.tmp.parent / (self.tmp.name + "-hook.sh")
        hook.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 1\n')
        hook.chmod(0o755)
        self.addCleanup(hook.unlink)
        self.git("config", "core.fsmonitor", str(hook))
        self.files("src/App.tsx")
        self.assertEqual(self.scan(), ["src/App.tsx"])
        self.assertFalse(marker.exists(), "the repository's fsmonitor ran")

    def test_without_git_the_build_folders_are_still_skipped(self):
        self.files("src/App.tsx", "dist/x.js", "generated/y.tsx")
        with mock.patch.object(L, "_git", return_value=None):
            self.assertEqual(self.scan(), ["generated/y.tsx", "src/App.tsx"])

    @unittest.skipUnless(os.name == "posix", "symbolic links")
    def test_a_symbolic_link_to_a_folder_is_not_followed(self):
        self.files("src/App.tsx", "elsewhere/x.tsx")
        (self.tmp / "src" / "linked").symlink_to(self.tmp / "elsewhere")
        self.assertEqual(self.scan("src"), ["App.tsx"])

    def test_the_empty_scan_message_says_what_was_skipped(self):
        self.files("dist/x.js")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = L.main([str(self.tmp)])
        self.assertEqual(code, 2)
        self.assertIn("outside build and dependency folders and what git "
                      "ignores", err.getvalue())



# ---------------------------------------------------------------------------
# R2 round 2: the independent review of the stage (R2A-1 to R2A-14)
# ---------------------------------------------------------------------------

class TestListenersElsewhere(unittest.TestCase):
    """R2A-1: Alpine's .outside, .away, .window and .document listen
    elsewhere; Vue's .right and .middle listen for other events."""

    def test_they_are_not_clicks_on_the_element(self):
        for path, src in (
                ("a.html", '<div x-show="open" @click.outside="open = false">'
                           'Contents</div>'),
                ("a.html", '<div @click.away="open = false">Info</div>'),
                ("a.html", '<div x-on:click.window="open = false">Info</div>'),
                ("a.html", '<div @click.document="open = false">Info</div>'),
                ("C.vue", '<template><div @click.right.prevent="menu">Row</div>'
                          '</template>'),
                ("C.vue", '<template><div @click.middle="open">Row</div>'
                          '</template>')):
            with self.subTest(src=src):
                self.assertEqual(findings(src, path, "bl-div-click"), [])

    def test_other_modifiers_still_click_the_element(self):
        for src in ('<div @click.once="go">x</div>',
                    '<div @click.capture.stop="go">x</div>',
                    '<div @click.ctrl.exact="go">x</div>'):
            with self.subTest(src=src):
                self.assertEqual(severities(src, "a.html", "bl-div-click"),
                                 [ERROR])

    def test_every_listener_counts(self):
        """Svelte 4 allows several; one that acts makes it a control."""
        for src in ('<div on:click|stopPropagation on:click={select}>Row</div>',
                    '<div on:click={select} on:click|stopPropagation>Row</div>'):
            with self.subTest(src=src):
                self.assertEqual(severities(src, "C.svelte", "bl-div-click"),
                                 [ERROR])
        self.assertEqual(severities('<div on:click|stopPropagation '
                                    'on:click|preventDefault>x</div>',
                                    "C.svelte", "bl-div-click"), [WARN])


class TestBoundAttributes(unittest.TestCase):
    """R2A-2: the newly read handlers met href, role and aria-hidden in
    spellings the rules did not read."""

    def test_a_link_with_a_bound_or_router_href_is_a_link(self):
        for path, src in (
                ("x.component.html", '<a class="nav-link" routerLink="/about" '
                                     '(click)="collapsed = true">About</a>'),
                ("x.component.html", '<a [routerLink]="[\'/home\']" '
                                     '(click)="collapsed = true">Home</a>'),
                ("x.component.html", '<a [href]="url" (click)="track()">D</a>'),
                ("x.component.html", '<a [attr.href]="url" (click)="t()">D</a>'),
                ("C.vue", '<template><a :href="url" @click="track">D</a>'
                          '</template>'),
                ("C.svelte", '<a {href} on:click={track}>Docs</a>'),
                ("el.ts", 'html`<a .href=${this.url} @click=${this.t}>D</a>`')):
            with self.subTest(src=src):
                self.assertEqual(findings(src, path, "bl-anchor-button"), [])

    def test_a_spread_may_supply_what_the_linter_cannot_see(self):
        self.assertEqual(severities('<template><a v-bind="$attrs" @click='
                                    '"track">Docs</a></template>', "C.vue",
                                    "bl-anchor-button"), [WARN])
        got = findings('<div {...props} onClick={go}>x</div>', "C.tsx",
                       "bl-div-click")
        self.assertEqual([f.severity for f in got], [WARN])
        self.assertIn("spread", got[0].message)

    def test_a_bound_role_or_aria_hidden_is_read(self):
        for path, src in (
                ("x.component.html", '<div [attr.role]="\'button\'" '
                 'tabindex="0" (keydown.enter)="t()" (click)="t()">x</div>'),
                ("x.component.html", '<div class="backdrop" '
                 '[attr.aria-hidden]="true" (click)="close()"></div>'),
                ("C.vue", '<template><div :aria-hidden="open" @click="close">'
                          'x</div></template>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [WARN])
        for path, src in (
                ("C.vue", '<template><div :aria-hidden="false" @click="close">'
                          'x</div></template>'),
                ("C.tsx", '<div aria-hidden="false" onClick={close}>x</div>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [ERROR])


class TestLitBindings(unittest.TestCase):
    """R2A-4: Lit's ${…} values were read as a bare token."""

    def test_a_lit_handler_is_read(self):
        self.assertEqual(severities('html`<div class="panel" @click=${(e) => '
                                    'e.stopPropagation()}>x</div>`', "el.ts",
                                    "bl-div-click"), [WARN])
        self.assertEqual(severities('html`<div @click="${() => this.go()}">x'
                                    '</div>`', "el.ts", "bl-div-click"), [ERROR])

    def test_an_interpolated_class_is_partial(self):
        self.assertEqual(severities('html`<button class="outline-none '
                                    '${this.ring}">x</button>`', "el.ts",
                                    "bl-outline-none-class"), [WARN])
        self.assertEqual(severities('<button type="button" class="btn {{ extra }}'
                                    ' outline-none">x</button>',
                                    "x.component.html",
                                    "bl-outline-none-class"), [WARN])


class TestWrapperPrecision(unittest.TestCase):
    """R2A-5: what N26 counted as focusable that is not."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_an_svg_use_href_is_no_link(self):
        for path, src in (
                ("C.tsx", '<div onClick={toggle}><svg><use href="#menu" />'
                          '</svg> Menu</div>'),
                ("a.html", '<div onclick="t()"><svg><use xlink:href="i.svg#x"/>'
                           '</svg> Like</div>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [ERROR])
        self.assertEqual(severities('<div onClick={go}><Foo href="/x" /></div>',
                                    "C.tsx", "bl-div-click"), [WARN])

    def test_commented_out_markup_renders_nothing(self):
        for path, src in (
                ("C.tsx", '<div onClick={toggle}>{/* <a href="/old">old</a> */}'
                          '<span>Menu</span></div>'),
                ("a.html", '<div onclick="t()"><!-- <a href="/old">old</a> -->'
                           '<span>Menu</span></div>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [ERROR])

    def test_text_that_looks_like_a_comment_is_not_one(self):
        """R2C-1: `//` and `/* */` are text in JSX children and templates,
        and a /* in a string opens nothing."""
        for path, src in (
                ("C.tsx", '<div onClick={go}>\n  // <a href="/x">x</a>\n'
                          '  <span>y</span></div>'),
                ("C.tsx", '<input type="file" accept="image/*" />\n'
                          '<div onClick={close}><a href="/a">A</a></div>'),
                ("C.tsx", '<Route path="/*" element={<Shell />} />\n'
                          '<div onClick={close}><a href="/a">A</a></div>'),
                ("C.vue", '<script setup>\nconst icons = import.meta.glob('
                          '"./icons/*.svg")\n</script>\n<template><div '
                          '@click="close"><a href="/a">A</a></div></template>'),
                ("a.html", '<p>Use /* to match all.</p><div onclick="t()">'
                           '<a href="/a">A</a></div>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-div-click"), [WARN])

    def test_a_local_inside_a_function_is_not_a_component(self):
        p = self.tmp / "sidebar.tsx"
        p.write_text('export function Sidebar({ items }) {\n  return (<nav>\n'
                     '    {items.map((item) => {\n'
                     '      const Icon = Icons[item.icon];\n'
                     '      return <div key={item.id} onClick={() => t(item)}>'
                     '<Icon /><span>{item.title}</span></div>;\n'
                     '    })}\n    <a href="/settings">Settings</a>\n'
                     '  </nav>);\n}\n')
        self.assertEqual(severities(p.read_text(), str(p), "bl-div-click"),
                         [ERROR])

    def test_a_default_import_reads_the_default_export(self):
        (self.tmp / "card.tsx").write_text(
            'export function CardAction() { return <button type="button">'
            'Share</button>; }\n'
            'export default function Card({ t }) { return <div><h3>{t}</h3>'
            '</div>; }\n')
        p = self.tmp / "page.tsx"
        p.write_text('import Card from "./card";\n'
                     'export const Page = () => <div onClick={open}>'
                     '<Card t="x" /></div>;\n')
        self.assertEqual(severities(p.read_text(), str(p), "bl-div-click"),
                         [ERROR])
        (self.tmp / "item.tsx").write_text(
            'const Item = () => <a href="/x">x</a>;\nexport default Item;\n')
        q = self.tmp / "menu.tsx"
        q.write_text('import Item from "./item";\n'
                     'export const Menu = () => <div onClick={close}><Item />'
                     '</div>;\n')
        self.assertEqual(severities(q.read_text(), str(q), "bl-div-click"),
                         [WARN])

    def test_a_re_export_is_followed(self):
        (self.tmp / "ui").mkdir()
        (self.tmp / "ui" / "nav-item.tsx").write_text(
            'export function NavItem() { return <a href="/x">x</a>; }\n')
        (self.tmp / "ui" / "index.ts").write_text(
            'export { NavItem } from "./nav-item";\n')
        p = self.tmp / "menu.tsx"
        p.write_text('import { NavItem } from "./ui";\n'
                     'export const Menu = () => <div onClick={close}>'
                     '<NavItem /></div>;\n')
        self.assertEqual(severities(p.read_text(), str(p), "bl-div-click"),
                         [WARN])

    def test_the_longest_path_alias_wins(self):
        (self.tmp / "tsconfig.json").write_text(
            '{"compilerOptions": {"paths": {"@/*": ["./src/*"], '
            '"@/components/*": ["./lib/components/*"]}}}')
        (self.tmp / "src" / "components").mkdir(parents=True)
        (self.tmp / "src" / "components" / "row.tsx").write_text(
            'export const Row = () => <p>x</p>;\n')
        (self.tmp / "lib" / "components").mkdir(parents=True)
        (self.tmp / "lib" / "components" / "row.tsx").write_text(
            'export const Row = () => <a href="/x">x</a>;\n')
        p = self.tmp / "src" / "menu.tsx"
        p.write_text('import { Row } from "@/components/row";\n'
                     'export const Menu = () => <div onClick={go}><Row />'
                     '</div>;\n')
        self.assertEqual(severities(p.read_text(), str(p), "bl-div-click"),
                         [WARN])

    def test_an_alias_outside_the_project_is_not_followed(self):
        """An absolute or UNC target (which Windows would open over the
        network) is never read."""
        (self.tmp / "package.json").write_text("{}")
        other = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, other, True)
        (other / "row.tsx").write_text('export const Row = () => <a href="/x">'
                                       'x</a>;\n')
        (self.tmp / "tsconfig.json").write_text(
            '{"compilerOptions": {"paths": {"@ext/*": ["%s/*"], '
            '"@unc/*": ["//server/share/*"]}}}' % other.as_posix())
        for spec in ("@ext/row", "@unc/row"):
            with self.subTest(spec=spec):
                p = self.tmp / "menu.tsx"
                p.write_text('import { Row } from "%s";\n'
                             'export const Menu = () => <div onClick={go}>'
                             '<Row /></div>;\n' % spec)
                self.assertEqual(severities(p.read_text(), str(p),
                                            "bl-div-click"), [ERROR])


class TestClassGuesses(unittest.TestCase):
    """R2A-6: expressions read as complete when part of them was not."""

    def test_an_unread_part_makes_a_warning(self):
        b = '<button type="button" className={%s}>x</button>'
        for expr in ('cn("outline-none", className as string)',
                     'cn("outline-none", className!)',
                     'cn("outline-none", ring satisfies string)',
                     'cn("outline-none", getRing?.())',
                     'cn("outline-none", { ...variantClasses })'):
            with self.subTest(expr=expr):
                self.assertEqual(severities(b % expr, "C.tsx",
                                            "bl-outline-none-class"), [WARN])
        for path, src in (
                ("x.component.html", '<button type="button" class="outline-none"'
                                     ' [ngClass]="ring$ | async">x</button>'),
                ("C.vue", '<template><button type="button" class="outline-none"'
                          ' v-bind="$attrs">x</button></template>'),
                ("C.tsx", '<button type="button" className="outline-none" '
                          '{...props}>x</button>')):
            with self.subTest(src=src):
                self.assertEqual(severities(src, path, "bl-outline-none-class"),
                                 [WARN])

    def test_a_condition_is_not_an_unread_part(self):
        b = '<button type="button" className={%s}>x</button>'
        self.assertEqual(severities(b % 'cn("outline-none", { active })',
                                    "C.tsx", "bl-outline-none-class"), [ERROR])

    def test_the_finding_names_the_attribute_that_removes_the_outline(self):
        src = ('<template><button\n  type="button"\n  :class="extra"\n'
               '  class="outline-none"\n>x</button></template>')
        got = findings(src, "C.vue", "bl-outline-none-class")
        self.assertEqual([(f.severity, f.line) for f in got], [(WARN, 4)])
        self.assertIn("outline-none", got[0].snippet)


class TestRobustness(unittest.TestCase):
    """R2A-7, R2A-8, R2A-11: crashes, hangs and slow spots."""

    def test_deeply_nested_template_literals_are_not_read(self):
        """500 template literals inside each other (2.5 KB): no
        RecursionError, and no error on what the linter could not read."""
        expr = "`${" * 500 + '"outline-none"' + "}`" * 500
        self.assertNotIn(ERROR, severities(
            '<button type="button" className={%s}>x</button>' % expr,
            "C.tsx", "bl-outline-none-class"))
        self.assertEqual(L._expr_classes(expr), ([], True))

    def test_a_file_the_linter_cannot_read_is_reported_not_fatal(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "a.tsx").write_text("<div>x</div>")
        (tmp / "b.tsx").write_text('<div onClick={go}>x</div>')
        real = L.lint_text

        def flaky(text, path):
            if path.endswith("a.tsx"):
                raise RecursionError("too deep")
            return real(text, path)
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(L, "lint_text", flaky), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = L.main([str(tmp), "--format", "json", "--fail-on", "warn"])
        data = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(sorted(f["rule_id"] for f in data["findings"]),
                         ["bl-div-click", "bl-lint-error"])

    def test_tsconfigs_that_would_hang_or_recurse(self):
        self.assertIsNone(L._loose_json("[" * 200000))
        t0 = time.monotonic()
        self.assertIsNone(L._loose_json('{"a": 1 /*' + "/*" * 100000))
        L._imports.cache_clear()
        L._imports("import" + " " * 20000 + "x")
        self.assertLess(time.monotonic() - t0, 2.0)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFOs")
    def test_a_fifo_named_tsconfig_json_is_not_read(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        os.mkfifo(tmp / "tsconfig.json")
        p = tmp / "menu.tsx"
        p.write_text('import { Row } from "@/row";\n'
                     'export const Menu = () => <div onClick={go}><Row />'
                     '</div>;\n')
        t0 = time.monotonic()
        self.assertEqual(severities(p.read_text(), str(p), "bl-div-click"),
                         [ERROR])
        self.assertLess(time.monotonic() - t0, 5.0)

    def test_many_wrappers_stay_linear(self):
        src = "".join('<div onclick="pick(%d)"><span>Item %d</span></div>\n'
                      % (i, i) for i in range(8000))
        t0 = time.monotonic()
        self.assertEqual(len(findings(src, "l.html", "bl-div-click")), 8000)
        self.assertLess(time.monotonic() - t0, 15.0)


class TestAnchorsAndDownEvents(unittest.TestCase):
    """R2A-13: a handler that only stops the event activates nothing."""

    def test_a_placeholder_link_that_only_prevents_the_default(self):
        self.assertEqual(severities('<a href="#" (click)="$event.'
                                    'preventDefault()">x</a>',
                                    "x.component.html", "bl-anchor-button"),
                         [WARN])
        self.assertEqual(severities('<a href="#" @click.prevent="go">x</a>',
                                    "a.html", "bl-anchor-button"), [ERROR])

    def test_a_down_event_that_only_prevents_the_default(self):
        for path, src in (
                ("C.vue", '<template><button type="button" @mousedown.prevent>'
                          'x</button></template>'),
                ("C.tsx", '<button type="button" onMouseDown={(e) => '
                          'e.preventDefault()}>x</button>')):
            with self.subTest(src=src):
                self.assertEqual(
                    findings(src, path, "bl-downevent-activation"), [])
        self.assertEqual(severities('<button type="button" onMouseDown={go}>x'
                                    '</button>', "C.tsx",
                                    "bl-downevent-activation"), [WARN])

    def test_blink_is_obsolete(self):
        """W3C made F47 (the blink element) obsolete: nothing blinks."""
        self.assertEqual(severities("<blink>x</blink>", "a.html",
                                    "bl-marquee-blink"), [WARN])
        self.assertEqual(severities("<marquee>x</marquee>", "a.html",
                                    "bl-marquee-blink"), [ERROR])


class TestTheScanRound2(unittest.TestCase):
    """R2A-3, R2A-9, R2A-10, and committed bundles."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def git(self, *args, cwd=None):
        subprocess.run(["git", "-C", str(cwd or self.tmp), *args], check=True,
                       capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t",
                            "GIT_AUTHOR_EMAIL": "t@example.com",
                            "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@example.com"})

    def write(self, rel, text="<div>x</div>\n"):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def scan(self, rel=".", notes=None):
        root = self.tmp / rel
        return sorted(p.relative_to(root).as_posix()
                      for p in collect([str(root)], notes))

    @unittest.skipUnless(GIT and os.name == "posix", "needs git and sh")
    def test_a_partial_clones_lazy_fetch_runs_nothing(self):
        """A missing .gitignore blob in a partial clone made git fetch it
        from the "promisor" remote, running the command the repository's
        own config names (remote.origin.uploadpack)."""
        theme = self.tmp / "outer" / "theme"
        self.write("outer/app/App.tsx")
        self.write("outer/theme/src/a.tsx")
        self.write("outer/theme/.gitignore", "dist-x/\n")
        self.git("init", "-q", cwd=theme)
        self.git("add", ".gitignore", "src/a.tsx", cwd=theme)
        self.git("commit", "-qm", "init", cwd=theme)
        oid = subprocess.run(["git", "-C", str(theme), "rev-parse",
                              "HEAD:.gitignore"], capture_output=True,
                             text=True, check=True).stdout.strip()
        self.git("update-index", "--skip-worktree", ".gitignore", cwd=theme)
        (theme / ".gitignore").unlink()
        (theme / ".git" / "objects" / oid[:2] / oid[2:]).unlink()
        marker = self.tmp / "MARKER"
        for key, value in (("core.repositoryformatversion", "1"),
                           ("extensions.partialClone", "origin"),
                           ("remote.origin.promisor", "true"),
                           ("remote.origin.url", str(theme / ".git")),
                           # Defeats a command-line protocol.allow=never.
                           ("protocol.file.allow", "always"),
                           ("remote.origin.uploadpack",
                            f'touch "{marker}"; false')):
            self.git("config", key, value, cwd=theme)
        # The attack is real: plain git runs the command.
        subprocess.run(["git", "-C", str(theme), "ls-files", "--others",
                        "--ignored", "--exclude-standard"],
                       capture_output=True)
        if not marker.exists():
            self.skipTest("this git does not lazy-fetch here")
        marker.unlink()
        self.assertEqual(self.scan("outer"), ["app/App.tsx", "theme/src/a.tsx"])
        self.assertFalse(marker.exists(), "the repository's command ran")

    @unittest.skipUnless(GIT, "needs git")
    def test_a_whitelist_gitignore_at_the_top(self):
        """`*` then `!*/` and `!src/**`: the top folder is never ignored."""
        self.git("init", "-q")
        (self.tmp / ".gitignore").write_text("*\n!*/\n!src/**\n!.gitignore\n")
        self.write("src/App.tsx")
        self.write("generated/x.tsx")
        self.assertEqual(self.scan(), ["src/App.tsx"])

    def test_when_git_refuses_the_scan_says_so(self):
        self.write("src/App.tsx")
        self.write("generated/x.tsx")
        refused = subprocess.CompletedProcess(
            [], 128, b"", b"fatal: detected dubious ownership in repository "
                          b"at '/x'\n")
        notes = []
        with mock.patch.object(L, "_git", return_value=refused):
            self.assertEqual(self.scan(notes=notes),
                             ["generated/x.tsx", "src/App.tsx"])
        self.assertEqual(len(notes), 1)
        self.assertIn("dubious ownership", notes[0])
        # Outside any work tree there is nothing to say.
        absent = subprocess.CompletedProcess(
            [], 128, b"", b"fatal: not a git repository (or any of the "
                          b"parent directories): .git\n")
        notes = []
        with mock.patch.object(L, "_git", return_value=absent):
            self.scan(notes=notes)
        self.assertEqual(notes, [])

    @unittest.skipUnless(GIT and os.name == "posix", "needs git")
    def test_git_is_never_taken_from_the_current_folder(self):
        """Windows runs a git.exe in the current folder before PATH's."""
        fake = self.write("git", "#!/bin/sh\nexit 0\n")
        fake.chmod(0o755)
        here = os.getcwd()
        self.addCleanup(os.chdir, here)
        self.addCleanup(L._git_exe.cache_clear)
        os.chdir(self.tmp)
        path = os.pathsep.join([".", str(self.tmp), os.path.dirname(GIT)])
        with mock.patch.dict(os.environ, {"PATH": path}):
            L._git_exe.cache_clear()
            found = L._git_exe()
        self.assertEqual(os.path.realpath(found), os.path.realpath(GIT))

    def test_committed_bundles_are_skipped_unless_named(self):
        self.write("src/App.tsx", "<div onClick={go}>x</div>\n")
        bundle = self.write("public/releases/main.3f2a9c.js",
                            "var a=1;" * 2000 + '"<div onclick=go()>x</div>"')
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = L.main([str(self.tmp), "--format", "json",
                           "--fail-on", "never"])
        data = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(data["files_scanned"], 1)
        self.assertTrue(any("minified" in n for n in data["notes"]))
        self.assertEqual({f["path"] for f in data["findings"]},
                         {str(self.tmp / "src" / "App.tsx")})
        with contextlib.redirect_stdout(io.StringIO()) as named:
            L.main([str(bundle), "--format", "json", "--fail-on", "never"])
        self.assertEqual(json.loads(named.getvalue())["files_scanned"], 1)



# ---------------------------------------------------------------------------
# R2 round 2: rule fixes from the citation review (R2B-2, R2B-3, F47)
# ---------------------------------------------------------------------------

from bellbriar_harness import checks_static as CS                  # noqa: E402
from bellbriar_harness.model import FAIL, NEEDS_REVIEW               # noqa: E402

HEADER = ('<header><nav><a href="/a">A</a><a href="/b">B</a>'
          '<a href="/c">C</a><a href="/d">D</a></nav></header>')
TEXT = "<p>" + "Long text about the shop. " * 20 + "</p>"


def page(body: str) -> CS.PageContext:
    return CS.PageContext.parse(
        '<!doctype html><html lang="en"><head><title>T</title></head>'
        f'<body>{body}</body></html>', path="x.html")


def verdicts(result) -> list:
    return [f.verdict for f in result.findings]


class TestRuleFixesFromTheCitationReview(unittest.TestCase):
    def test_a_named_landmark_the_content_starts_in_bypasses(self):
        """ARIA11 and ACT b40fd1: a named region or form past the blocks.
        A complementary landmark, an unnamed section or a region inside the
        header does not."""
        for body, expected in (
                (HEADER + '<section aria-label="Products">' + TEXT
                 + "</section>", [NEEDS_REVIEW]),
                (HEADER + '<form aria-label="Find a flight">' + TEXT
                 + '<input aria-label="From"></form>', [NEEDS_REVIEW]),
                (HEADER + '<div role="region" aria-labelledby="h">'
                 '<span id="h">News</span>' + TEXT + "</div>", [NEEDS_REVIEW]),
                (HEADER + "<section>" + TEXT + "</section>", [FAIL]),
                (HEADER + '<aside aria-label="Offers">' + TEXT + "</aside>",
                 [FAIL]),
                ('<header><section aria-label="Promo">x</section>'
                 '<nav><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a>'
                 "</nav></header>" + TEXT, [FAIL])):
            with self.subTest(body=body[:120]):
                got = CS.check_skip_link(page(body))
                self.assertEqual(verdicts(got), expected)
                if expected == [NEEDS_REVIEW]:
                    self.assertIn("a landmark the content starts in",
                                  got.findings[0].message)

    def test_an_iframe_out_of_the_tab_order_or_decorative_needs_no_name(self):
        """ACT cae760: not applicable."""
        for frame in ('<iframe src="/a" tabindex="-1"></iframe>',
                      '<iframe src="/a" role="presentation"></iframe>',
                      '<iframe src="/a" role="none"></iframe>'):
            with self.subTest(frame=frame):
                self.assertEqual(verdicts(CS.check_iframe_title(page(frame))),
                                 [])
        for frame in ('<iframe src="/a"></iframe>',
                      '<iframe src="/a" tabindex="0"></iframe>',
                      '<iframe src="/a" tabindex="x"></iframe>'):
            with self.subTest(frame=frame):
                self.assertEqual(verdicts(CS.check_iframe_title(page(frame))),
                                 [FAIL])

    def test_blink_moves_nothing(self):
        """W3C made F47 obsolete: no current browser makes <blink> blink."""
        got = CS.check_marquee_blink(page("<blink>Sale</blink>"))
        self.assertEqual(verdicts(got), [NEEDS_REVIEW])
        self.assertIn("obsolete", got.findings[0].message)
        self.assertEqual(verdicts(CS.check_marquee_blink(
            page("<marquee>Sale</marquee>"))), [FAIL])

    def test_four_rules_resting_on_proposed_act_rules_are_heuristic(self):
        from bellbriar_harness.engine import load_rulebook
        basis = {r["id"]: r.get("verdict_basis")
                 for r in load_rulebook()["rules"]}
        for rid in ("bb-iframe-title", "bb-aria-required-children",
                    "bb-aria-required-parent"):
            with self.subTest(rule=rid):
                self.assertEqual(basis[rid], "heuristic")
        # Part R3: axe-core 4.12.1 never fails th-has-data-cells (a header
        # with no data cell is a result it cannot decide), so the rule
        # only asks for review. Never sc either way.
        self.assertEqual(basis["bb-th-data-cells"], "review")



# ---------------------------------------------------------------------------
# R2 round 3: the review of the round-2 fixes (R2C-1 to R2C-8)
# ---------------------------------------------------------------------------

class TestContentPassedIn(unittest.TestCase):
    """R2C-2: a wrapper whose content comes from its caller (a slot,
    children) may hold the controls; the linter cannot see them."""

    def test_passed_in_content_is_a_warning(self):
        for path, src in (
                ("C.vue", '<template><div @click="toggle"><slot /></div>'
                          '</template>'),
                ("C.tsx", 'const Card = ({ children, onClick }) => <div '
                          'onClick={onClick}>{children}</div>;'),
                ("C.tsx", '<div onClick={go}>{props.children}</div>'),
                ("C.svelte", '<div onclick={go}>{@render children()}</div>'),
                ("x.component.html", '<div (click)="go()"><ng-content>'
                                     '</ng-content></div>'),
                ("el.ts", 'html`<div @click=${this.go} @keydown=${this.key}>'
                          '<slot name="nav"></slot></div>`'),
                ("C.vue", '<template><div @click="go"><component :is="item">'
                          '</component></div></template>'),
                ("C.tsx", '<div onClick={go} dangerouslySetInnerHTML='
                          '{{ __html: html }} />')):
            with self.subTest(src=src):
                got = findings(src, path, "bl-div-click")
                self.assertEqual([f.severity for f in got], [WARN])
        got = findings('<div onClick={go}>{children}</div>', "C.tsx",
                       "bl-div-click")
        self.assertIn("content passed in", got[0].message)

    def test_content_the_linter_sees_is_still_read(self):
        for src in ('<div onClick={toggle}><span>Menu</span><ChevronDownIcon />'
                    '</div>',
                    '<div onClick={go}>{label}</div>',
                    '<div onClick={go}>{/* {children} */}<span>x</span></div>'):
            with self.subTest(src=src):
                self.assertEqual(severities(src, "C.tsx", "bl-div-click"),
                                 [ERROR])


class TestDefaultExports(unittest.TestCase):
    """R2C-3: a default export the linter cannot pin to a declaration was
    read as markup-free; it is read as the whole module."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_with(self, card: str, wrapper_import='import Card from "./card";'):
        (self.tmp / "card.tsx").write_text(card)
        p = self.tmp / "page.tsx"
        p.write_text(wrapper_import + '\nexport const Page = () => <div '
                     'onClick={open}><Card /></div>;\n')
        return severities(p.read_text(), str(p), "bl-div-click")

    def test_every_default_export_form(self):
        link = 'function Card() { return <a href="/x">x</a>; }\n'
        for tail in ('export default connect(map)(Card);',
                     'export default withStyles(s)(Card);',
                     'export default Card; // main',
                     'export default /* x */ Card;',
                     'export { Card as default };',
                     'module.exports = Card;'):
            with self.subTest(tail=tail):
                self.assertEqual(self.run_with(link + tail + "\n"), [WARN])
        plain = 'function Card() { return <p>x</p>; }\n'
        for tail in ('export default memo(Card);', 'export { Card as default };'):
            with self.subTest(tail=tail):
                self.assertEqual(self.run_with(plain + tail + "\n"), [ERROR])

    def test_a_named_export_under_another_name(self):
        self.assertEqual(self.run_with(
            'function Inner() { return <a href="/x">x</a>; }\n'
            'export { Inner as Card };\n',
            'import { Card } from "./card";'), [WARN])

    def test_an_import_beside_a_name_that_starts_with_from(self):
        """R2C-8d: `import Card, { fromApi } from …` was dropped."""
        self.assertEqual(self.run_with(
            'export const fromApi = 1;\n'
            'export default function Card() { return <a href="/x">x</a>; }\n',
            'import Card, { fromApi } from "./card";'), [WARN])

    def test_many_wrappers_of_a_component_from_a_large_module(self):
        """R2C-6: each wrapper read the module again."""
        big = "".join(f"export const V{i} = () => <p>{i}</p>;\n"
                      for i in range(4000))
        (self.tmp / "card.tsx").write_text(
            big + 'export default function Card() { return <p>x</p>; }\n')
        p = self.tmp / "page.tsx"
        p.write_text('import Card from "./card";\nexport const Page = () => '
                     '<>' + "<div onClick={open}><Card /></div>\n" * 3000
                     + "</>;\n")
        t0 = time.monotonic()
        got = severities(p.read_text(), str(p), "bl-div-click")
        self.assertEqual(len(got), 3000)
        self.assertLess(time.monotonic() - t0, 20.0)


class TestRound3Details(unittest.TestCase):
    def test_a_plain_lit_boolean_binding_is_unknown(self):
        """R2C-4: Lit writes muted=${false} as muted="false", which mutes;
        only ?muted=${false} takes it away."""
        rule = "bl-autoplay-media"
        self.assertNotIn(ERROR, severities(
            'html`<video src="a.mp4" autoplay muted=${false}></video>`',
            "el.ts", rule))
        self.assertEqual(severities(
            'html`<video src="a.mp4" autoplay ?muted=${false}></video>`',
            "el.ts", rule), [ERROR])

    def test_a_file_named_as_minified_is_skipped(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "skin.min.css").write_text("a{outline:0}\n")
        (tmp / "app.css").write_text("b{color:red}\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([str(tmp), "--format", "json", "--fail-on", "never"])
        self.assertEqual(json.loads(out.getvalue())["files_scanned"], 1)

    def test_a_long_data_uri_is_not_a_minified_bundle(self):
        """R2C-5: a hand-written file with an embedded image or font."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        (tmp / "src").mkdir()
        (tmp / "src" / "Logo.js").write_text(
            'const logo = "data:image/png;base64,' + "A" * 20000 + '";\n'
            'export const L = () => <div onClick={go}>x</div>;\n')
        (tmp / "src" / "fonts.css").write_text(
            "@font-face{src:url(data:font/woff2;base64," + "B" * 20000
            + ")}\nbutton:focus{outline:none}\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), \
                contextlib.redirect_stderr(io.StringIO()):
            L.main([str(tmp), "--format", "json", "--fail-on", "never"])
        data = json.loads(out.getvalue())
        self.assertEqual(data["files_scanned"], 2)
        self.assertEqual(data["errors"], 2)

    def test_svelte_class_directives_keep_their_variants(self):
        """R2C-8a: Svelte keeps everything after class: as the name."""
        self.assertEqual(severities(
            '<button type="button" class="outline-none" '
            'class:focus-visible:ring-2={on}>x</button>', "C.svelte",
            "bl-outline-none-class"), [WARN])
        self.assertEqual(severities(
            '<button type="button" class:focus:outline-none={flat}>x</button>',
            "C.svelte", "bl-outline-none-class"), [WARN])

    def test_alpine_modifiers_mean_nothing_to_vue(self):
        """R2C-8b: Vue reads unknown modifiers only on key events."""
        self.assertEqual(severities('<template><div @click.outside="close">x'
                                    '</div></template>', "C.vue",
                                    "bl-div-click"), [ERROR])
        self.assertEqual(severities('<div @click.outside="close">x</div>',
                                    "a.html", "bl-div-click"), [])

    def test_where_a_spread_sits(self):
        """R2C-8c: an explicit class after a JSX or Svelte spread wins."""
        rule = "bl-outline-none-class"
        self.assertEqual(severities('<button type="button" {...props} '
                                    'className="outline-none">x</button>',
                                    "C.tsx", rule), [ERROR])
        self.assertEqual(severities('<button type="button" className="outline-'
                                    'none" {...props}>x</button>', "C.tsx",
                                    rule), [WARN])
        self.assertEqual(severities('<a href="#" {...p} onClick={go}>x</a>',
                                    "C.tsx", "bl-anchor-button"), [WARN])

    def test_teleport_to_is_not_a_link(self):
        """R2C-8e: `to` is not a link's prop on every component."""
        for src in ('<div onClick={go}><Teleport to="body"><p>x</p></Teleport>'
                    '</div>',
                    '<div onClick={go}><Navigate to="/login" /></div>'):
            with self.subTest(src=src):
                self.assertEqual(severities(src, "C.tsx", "bl-div-click"),
                                 [ERROR])

    def test_a_bound_href_with_a_modifier(self):
        """R2C-8f: Vue's :href.prop."""
        self.assertEqual(severities('<template><a :href.prop="url" @click="t">'
                                    'x</a></template>', "C.vue",
                                    "bl-anchor-button"), [])

    def test_a_comment_in_a_class_expression(self):
        """R2C-8g: the identifier before a comment is still a value."""
        self.assertEqual(severities('<button type="button" className={cn('
                                    '"outline-none", focusRing // theme\n)}>x'
                                    '</button>', "C.tsx",
                                    "bl-outline-none-class"), [WARN])


class TestTheScanRound3(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def write(self, rel, text="<div>x</div>\n"):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def scan(self, notes=None):
        return sorted(p.relative_to(self.tmp).as_posix()
                      for p in collect([str(self.tmp)], notes))

    @unittest.skipUnless(GIT, "needs git")
    def test_a_broken_nested_git_file_keeps_the_outer_rules(self):
        """R2C-8h: a stale worktree or submodule's .git file makes no
        repository; git reads the folder as part of the one around it."""
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        (self.tmp / ".gitignore").write_text("*.gen.tsx\n")
        self.write("app/App.tsx")
        self.write("old/x.gen.tsx")
        self.write("old/y.tsx")
        (self.tmp / "old" / ".git").write_text("gitdir: /nowhere/at/all\n")
        notes = []
        self.assertEqual(self.scan(notes), ["app/App.tsx", "old/y.tsx"])
        self.assertEqual(notes, [])

    @unittest.skipUnless(GIT and hasattr(os, "mkfifo"), "needs git and FIFOs")
    def test_a_git_that_stalls_is_asked_once(self):
        """R2C-7: FIFOs among nested repositories' ignore files stalled
        each git call for the whole timeout."""
        for name in ("a", "b", "c", "d"):
            self.write(f"{name}/src/x.tsx")
            subprocess.run(["git", "init", "-q", str(self.tmp / name)],
                           check=True)
            os.mkfifo(self.tmp / name / ".gitignore")
        notes = []
        t0 = time.monotonic()
        with mock.patch.object(L, "_GIT_TIMEOUT", 2):
            got = self.scan(notes)
        self.assertLess(time.monotonic() - t0, 6.0)
        self.assertEqual(len(got), 4)
        self.assertEqual(len(notes), 1)
        self.assertIn("stops asking it", notes[0])

    @unittest.skipUnless(os.name == "posix", "symbolic links")
    def test_a_link_to_a_file_outside_the_folder_is_not_linted(self):
        """R2C-8i: its lines would be printed as snippets."""
        secret = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, secret, True)
        (secret / "env.html").write_text("API_TOKEN=s3cr3t <marquee>x</marquee>")
        self.write("src/App.tsx")
        (self.tmp / "src" / "page.html").symlink_to(secret / "env.html")
        (self.tmp / "src" / "same.html").symlink_to(self.tmp / "src" / "App.tsx")
        notes = []
        self.assertEqual(self.scan(notes), ["src/App.tsx", "src/same.html"])
        self.assertTrue(any("symbolic link" in n for n in notes))
        named = self.tmp / "src" / "page.html"
        self.assertEqual(collect([str(named)]), [named])



# ---------------------------------------------------------------------------
# R2 round 4: the review of the citation fixes (R2E-1 to R2E-11)
# ---------------------------------------------------------------------------

from bellbriar_harness import axe as A                              # noqa: E402
from bellbriar_harness.engine import load_rulebook, run_page        # noqa: E402
from tests.test_rendered_rules import (P, attr, rerun,              # noqa: E402
                                       run_record, snapshot)
from tests.test_rendered_rules import findings as found_by          # noqa: E402
from tests.test_rendered_rules import mark as axe_mark              # noqa: E402

RULES = {r["id"]: r for r in load_rulebook()["rules"]}


def run(body: str):
    return run_page('<!doctype html><html lang="en"><head><title>T</title>'
                    f'</head><body><main>{body}</main></body></html>',
                    "x.html", load_rulebook())


def by_rule(page_result) -> dict:
    out: dict = {}
    for r in page_result.results:
        for f in r.findings:
            out.setdefault(r.rule_id, []).append(f)
    return out


class TestOneRuleOneBasis(unittest.TestCase):
    """R2E-1, R2E-2: a report prints every criterion a rule cites beside
    its FAIL, and labels the FAIL by the rule's basis. bb-widget-name
    failed progress bars (no W3C basis), images (1.1.1) and controls
    (4.1.2, F68) under one sc label and both criteria; bb-control-label
    named 3.3.2 and 1.3.1, which its ACT rule does not require."""

    def test_each_kind_of_unnamed_element_fails_under_its_own_rule(self):
        for body, rule in (('<div role="menuitem"></div>', "bb-widget-name"),
                           ('<div role="tab"></div>', "bb-widget-name"),
                           ('<div role="img"></div>', "bb-role-img-name"),
                           ('<i role="img" class="icon"></i>',
                            "bb-role-img-name"),
                           ('<div role="progressbar" aria-valuenow="40">'
                            "</div>", "bb-progress-name"),
                           ('<div role="meter" aria-valuenow="4"></div>',
                            "bb-progress-name")):
            with self.subTest(body=body):
                got = {rid: [f.verdict for f in fs]
                       for rid, fs in by_rule(run(body)).items()
                       if rid in ("bb-widget-name", "bb-role-img-name",
                                  "bb-progress-name")}
                self.assertEqual(got, {rule: [FAIL]})

    def test_each_rule_cites_only_what_its_fail_is_named_for(self):
        expected = {"bb-widget-name": ("sc", ["4.1.2"]),
                    "bb-role-img-name": ("sc", ["1.1.1"]),
                    "bb-progress-name": ("heuristic", ["1.1.1"]),
                    "bb-control-label": ("sc", ["4.1.2"]),
                    "bb-aria-hidden-focus": ("sc", ["4.1.2"])}
        for rid, (basis, sc) in expected.items():
            with self.subTest(rule=rid):
                self.assertEqual((RULES[rid]["verdict_basis"],
                                  RULES[rid]["sc"]), (basis, sc))
        self.assertEqual(RULES["bb-widget-name"]["w3c_failures"], ["F68"])
        self.assertEqual([a["id"] for a in RULES["bb-role-img-name"]
                          ["act_rules"]], ["23a2a8"])

    def test_an_empty_tooltip_is_a_review_even_when_shown(self):
        """A tooltip is not a control; W3C names no failure for it."""
        self.assertEqual([f.verdict for f in by_rule(
            run('<div role="tooltip"></div>'))["bb-widget-name"]],
            [NEEDS_REVIEW])
        page = rerun(snapshot('<div role="tooltip" id="t"></div>',
                              root=attr(P + "-hidden", "recorded")))
        got = found_by(page, "bb-widget-name")
        self.assertEqual([f.verdict for f in got], [NEEDS_REVIEW])
        self.assertIn("while shown", got[0].message)

    def test_axe_rules_the_split_replaces_name_the_new_rules(self):
        self.assertEqual(A.NOT_RUN["aria-progressbar-name"], "bb-progress-name")
        self.assertEqual(A.NOT_RUN["aria-meter-name"], "bb-progress-name")
        self.assertEqual(A.NOT_RUN["role-img-alt"], "bb-role-img-name")


class TestABrokenReferenceIsOneDefect(unittest.TestCase):
    """R2E-3: bb-aria-ref failed an element its own name rule already
    failed (an image under 1.1.1 and again under 4.1.2 as F68, which covers
    only controls), and an iframe cae760 calls inapplicable."""

    def test_the_name_rule_fails_and_the_reference_is_reviewed(self):
        for body, rule, fails in (
                ('<button aria-labelledby="gone"></button>', "bb-button-name",
                 True),
                ('<a href="/x" aria-labelledby="gone"></a>', "bb-link-name",
                 True),
                ('<input aria-labelledby="gone">', "bb-control-label", True),
                ('<div role="tab" aria-labelledby="gone"></div>',
                 "bb-widget-name", True),
                ('<img src="a.png" aria-labelledby="gone">', "bb-img-alt",
                 True),
                ('<div role="img" aria-labelledby="gone"></div>',
                 "bb-role-img-name", True),
                ('<iframe src="/a" tabindex="-1" aria-labelledby="gone">'
                 "</iframe>", "bb-iframe-title", False),
                ("<details><summary aria-labelledby=\"gone\"></summary>x"
                 "</details>", "bb-summary-name", False)):
            with self.subTest(body=body):
                got = by_rule(run(body))
                ref = got["bb-aria-ref"]
                self.assertEqual([(f.verdict, f.impact) for f in ref],
                                 [(NEEDS_REVIEW, "moderate")])
                self.assertIn(f"which {rule} decides", ref[0].message)
                fails_here = [rid for rid, fs in got.items()
                              if any(f.verdict == FAIL for f in fs)]
                self.assertEqual(fails_here, [rule] if fails else [])

    def test_the_rule_never_fails(self):
        self.assertEqual(RULES["bb-aria-ref"]["verdict_basis"], "review")
        self.assertNotIn("w3c_failures", RULES["bb-aria-ref"])
        self.assertIn("in a browser run", by_rule(run(
            '<object data="a.svg" aria-labelledby="gone"></object>'))
            ["bb-aria-ref"][0].message)


class TestXmlLangAlone(unittest.TestCase):
    """R2E-4 (L60): axe-core's valid-lang fails an invalid xml:lang, which
    W3C's ACT rule de46e4 does not test and HTML ignores."""

    MSG = axe_mark(("valid-lang", "fail", "serious",
                    "Value of lang attribute not included in the list of "
                    "valid languages [axe-core 4.12.1 valid-lang]"))

    def verdict(self, attrs: str) -> list:
        others = sorted(set(A.AXE_RULES.values()) - {"valid-lang"})
        html = snapshot(f'<p {attrs}{attr(P + "-axe", self.MSG)}>Bonjour</p>',
                        root=attr(P + "-axe-run",
                                  run_record(["valid-lang"], others)))
        return [(f.verdict, f.impact) for f in
                found_by(rerun(html), "bb-element-lang")]

    def test_only_a_result_lang_can_explain_fails(self):
        self.assertEqual(self.verdict('lang="fr" xml:lang="francais"'),
                         [(NEEDS_REVIEW, "minor")])
        self.assertEqual(self.verdict('xml:lang="francais"'),
                         [(NEEDS_REVIEW, "minor")])
        self.assertEqual(self.verdict('lang="" xml:lang="francais"'),
                         [(NEEDS_REVIEW, "minor")])
        self.assertEqual(self.verdict('lang="francais"'), [(FAIL, "serious")])
        self.assertEqual(self.verdict('lang="francais" xml:lang="fr"'),
                         [(FAIL, "serious")])


class TestTheLandmarkTheContentStartsIn(unittest.TestCase):
    """R2E-5: the fallback took a named region inside role=banner or a
    second header, a consent region after the footer, a site search, a
    newsletter form after the content, a name from an empty element, and a
    region whose only text was aria-hidden."""

    HEAD = ('<header><a href="/">Logo</a></header><nav><a href="/a">A</a>'
            '<a href="/b">B</a><a href="/c">C</a></nav>')
    TXT = "<p>" + "Lorem ipsum dolor sit amet. " * 3 + "</p>"

    def check(self, body: str) -> list:
        return verdicts(CS.check_skip_link(page(self.HEAD + body)))

    def test_a_landmark_that_opens_the_content_bypasses(self):
        for body in (f'<section aria-label="Content">{self.TXT}</section>',
                     '<form aria-label="Contact us"><label>Email <input>'
                     f'</label>{self.TXT}</form>',
                     f'<div role="region" aria-labelledby="h"><p id="h">News'
                     f'</p>{self.TXT}</div>'):
            with self.subTest(body=body[:60]):
                self.assertEqual(self.check(body), [NEEDS_REVIEW])

    def test_others_do_not(self):
        t = self.TXT
        for body in (
                f'<div role="banner"><section aria-label="X">{t}</section>'
                f'</div>{t}',
                f'<header><section aria-label="Hero">{t}</section></header>',
                f'{t}<footer><a href="/x">x</a></footer>'
                '<section aria-label="Cookies"><p>We use cookies</p></section>',
                '<form aria-label="Search"><input type="search" '
                f'aria-label="q"></form>{t}',
                f'<form aria-label="Site search"><input aria-label="q"></form>{t}',
                f'<search><form aria-label="Find"><input aria-label="q">'
                f'</form></search>{t}',
                f'{t}<form aria-label="Newsletter"><input aria-label="email">'
                "</form>",
                f'<section aria-labelledby="e"><span id="e"></span>{t}'
                "</section>",
                '<section aria-label="Content"><p aria-hidden="true">Hidden'
                f"</p></section>{t}",
                f'<p>Intro.</p><section aria-label="Content">{t}</section>'):
            with self.subTest(body=body[:70]):
                self.assertEqual(self.check(body), [FAIL])

    def test_a_landmark_around_the_blocks_bypasses_nothing(self):
        got = verdicts(CS.check_skip_link(page(
            f'<section aria-label="All">{self.HEAD}{self.TXT}</section>')))
        self.assertEqual(got, [FAIL])


class TestAMarqueeThatMoves(unittest.TestCase):
    """R2E-6: F16 needs moving content with no way to pause it, which
    markup cannot show; hidden and still marquees failed too."""

    def check(self, body: str) -> list:
        return verdicts(CS.check_marquee_blink(page(body)))

    def test_what_moves_and_what_may_stop(self):
        self.assertEqual(self.check("<marquee>Sale</marquee>"), [FAIL])
        for body in ("<marquee hidden>Sale</marquee>",
                     '<marquee style="display:none">Sale</marquee>',
                     '<marquee scrollamount="0">Sale</marquee>'):
            with self.subTest(body=body):
                self.assertEqual(self.check(body), [])
        for body in ('<marquee behavior="slide">Sale</marquee>',
                     '<marquee loop="3">Sale</marquee>',
                     '<marquee onmouseover="this.stop()" '
                     'onmouseout="this.start()">Sale</marquee>',
                     '<marquee id="m">Sale</marquee><button onclick="'
                     "document.getElementById('m').stop()\">Pause</button>"):
            with self.subTest(body=body):
                self.assertEqual(self.check(body), [NEEDS_REVIEW])

    def test_one_a_stylesheet_hides_is_not_checked(self):
        hidden = attr(P + "-hidden", "display")
        page_ = rerun(snapshot(f"<marquee{hidden}>Sale</marquee>",
                               root=attr(P + "-hidden", "recorded")))
        self.assertEqual(found_by(page_, "bb-marquee-blink"), [])

    def test_the_basis_is_heuristic(self):
        self.assertEqual(RULES["bb-marquee-blink"]["verdict_basis"],
                         "heuristic")
        self.assertNotIn("w3c_failures", RULES["bb-marquee-blink"])


class TestSmallerRuleFixes(unittest.TestCase):
    """R2E-8, R2E-10, R2E-11, and the notes R2E-9 found wrong."""

    def test_a_focusable_element_with_no_role_is_a_probable_failure(self):
        """R2E-8: F59 names a control made with script; focus alone does
        not show the element is one (a focusable scroll container)."""
        self.assertEqual(RULES["bb-control-role"]["verdict_basis"],
                         "heuristic")
        got = CS.check_control_role(page(
            '<div tabindex="0" role="scroll-area">Text</div>'))
        self.assertEqual(verdicts(got), [FAIL])
        self.assertIn("if it is a control", got.findings[0].message)

    def test_cae760_reads_the_first_role_a_browser_knows(self):
        """R2E-10: role="foo none" is none; a decorative iframe needs no
        name even in the tab order (Inapplicable Example 4)."""
        for frame in ('<iframe src="/a" role="foo none"></iframe>',
                      '<iframe src="/a" role="none" tabindex="0"></iframe>'):
            with self.subTest(frame=frame):
                self.assertEqual(verdicts(CS.check_iframe_title(page(frame))),
                                 [])
        self.assertEqual(verdicts(CS.check_iframe_title(page(
            '<iframe src="/a" role="foo"></iframe>'))), [FAIL])

    def test_viewport_keywords_are_numbers(self):
        """R2E-11: b4f0c3's Failed Example 4 (maximum-scale=yes is 1.0)."""
        for content, expected in (("maximum-scale=yes", [FAIL]),
                                  ("maximum-scale=no", [FAIL]),
                                  ("maximum-scale=device-width", []),
                                  ("maximum-scale=-1", []),
                                  ("width=device-width, maximum-scale=1.5",
                                   [FAIL])):
            with self.subTest(content=content):
                got = CS.check_viewport_zoom(CS.PageContext.parse(
                    '<!doctype html><html lang="en"><head><title>T</title>'
                    f'<meta name="viewport" content="{content}"></head>'
                    "<body><p>x</p></body></html>", path="x.html"))
                self.assertEqual(verdicts(got), expected)

    def test_the_notes_say_what_axe_core_does_with_an_empty_container(self):
        """R2E-9: it reviews an empty list or tablist; only a feed, row or
        suggestion that owns nothing fails."""
        note = RULES["bb-aria-required-children"]["notes"]
        self.assertIn("fails only as a feed, a row or a suggestion", note)
        self.assertNotIn("for most roles", note)


if __name__ == "__main__":
    unittest.main(verbosity=2)
