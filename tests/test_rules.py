from migrator.lint import lint
from migrator.rules import convert, split_args


def conv(line):
    return convert(line)["code"]


def test_visit_and_click():
    assert "await page.goto('/login');" in conv("cy.visit('/login')")
    assert "await page.locator('#go').click();" in conv("cy.get('#go').click()")


def test_type_becomes_fill_and_enter():
    out = conv("cy.get('#q').type('abc{enter}')")
    assert "fill('abc')" in out and "press('Enter')" in out


def test_assertions():
    assert "toBeHidden()" in conv("cy.get('#x').should('not.be.visible')")
    assert "toHaveCount(3)" in conv("cy.get('li').should('have.length', 3)")
    assert "toHaveURL(new RegExp('/home'))" in conv("cy.url().should('include', '/home')")


def test_unsupported_leaves_todo_and_fails_gate():
    res = convert("cy.intercept('GET', '/api')")
    assert res["todo_lines"]
    assert not lint(res["code"])["passed"]


def test_structure_and_parity():
    src = "describe('a', () => {\n  it('b', () => {\n    cy.visit('/')\n  })\n})"
    res = convert(src)
    assert "test('b', async ({ page }) => {" in res["code"]
    assert lint(res["code"], src)["passed"]


def test_split_args_respects_quotes():
    assert split_args("'a,b', 2") == ["'a,b'", "2"]


def test_async_it_and_hooks():
    src = "describe('a', () => {\n  beforeEach(async () => {\n    cy.visit('/')\n  })\n  it('b', async () => {\n    cy.get('#x').click()\n  })\n})"
    out = convert(src)["code"]
    assert "test.beforeEach(async ({ page }) => {" in out
    assert "test('b', async ({ page }) => {" in out


def test_sample_needs_agent():
    from pathlib import Path
    src = Path(__file__).parent.parent.joinpath("samples", "login.cy.js").read_text(encoding="utf-8")
    res = convert(src)
    assert len(res["todo_lines"]) == 3          # intercept, aliased wait, multi-line chain
    assert not lint(res["code"], src)["passed"]  # the gate must reject the unfinished draft
