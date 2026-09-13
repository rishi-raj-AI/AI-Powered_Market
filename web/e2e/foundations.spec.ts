import {expect, test} from '@playwright/test';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readFileSync} from 'node:fs';
import ts from 'typescript';

// Compile isolated server-rendered specimens without adding a production route.
function loadUi(name: string): any {
  const source = readFileSync(`${__dirname}/../components/ui/${name}.tsx`, 'utf8');
  const {outputText} = ts.transpileModule(source, {
    compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS},
  });
  const module = {exports: {}};
  const load = (id: string) => id.startsWith('./') ? loadUi(id.slice(2)) : require(id);
  new Function('require', 'module', 'exports', outputText)(load, module, module.exports);
  return module.exports;
}

const {Button}: typeof import('../components/ui/Button') = loadUi('Button');
const {FormField}: typeof import('../components/ui/FormField') = loadUi('FormField');
const {Notice, Loading, Empty, Retry}: typeof import('../components/ui/Feedback') = loadUi('Feedback');
const {PriceBreakdown}: typeof import('../components/ui/PriceBreakdown') = loadUi('PriceBreakdown');
const css = ['globals.css', 'design-tokens.css']
  .map(file => readFileSync(`${__dirname}/../app/${file}`, 'utf8'))
  .join('\n');
const render = (node: Parameters<typeof renderToStaticMarkup>[0]) =>
  `<meta name="viewport" content="width=device-width, initial-scale=1"><style>${css}</style>${renderToStaticMarkup(node)}`;

test('loading Button has meaningful text and prevents native activation', async ({page}) => {
  await page.setContent(render(h('div', null,
    h(Button, {busy: true, loadingLabel: 'Saving address…'}, 'Save address'),
    h(Button, {busy: true}, 'Continue'),
    h(Button, {disabled: true}, 'Unavailable'),
  )));
  await expect(page.getByRole('button', {name: 'Saving address…'})).toHaveAttribute('aria-busy', 'true');
  for (const name of ['Saving address…', 'Working…', 'Unavailable']) {
    await expect(page.getByRole('button', {name})).toBeDisabled();
  }
  await page.evaluate(() => {
    document.body.dataset.clicked = 'no';
    document.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => { document.body.dataset.clicked = 'yes'; });
      button.click();
    });
  });
  await expect(page.locator('body')).toHaveAttribute('data-clicked', 'no');
});

test('all Button intents have token focus, native keyboard behavior, and minimum target', async ({page}) => {
  await page.setContent(render(h('div', null,
    ...(['primary', 'secondary', 'tertiary', 'destructive'] as const)
      .map(intent => h(Button, {intent, key: intent}, 'Action')),
  )));
  for (const button of await page.getByRole('button').all()) {
    await button.focus();
    await expect(button).toBeFocused();
    await button.evaluate(element => {
      element.setAttribute('data-activations', '0');
      element.addEventListener('click', () => element.setAttribute(
        'data-activations',
        String(Number(element.getAttribute('data-activations')) + 1),
      ));
    });
    await page.keyboard.press('Enter');
    await page.keyboard.press('Space');
    await expect(button).toHaveAttribute('data-activations', '2');
    await expect(button).toHaveCSS('outline-style', 'solid');
    await expect(button).toHaveCSS('outline-width', '2px');
    await expect(button).toHaveCSS('outline-offset', '2px');
    await expect(button).toHaveCSS('outline-color', 'rgb(20, 91, 51)');
    await expect(button).toHaveCSS('overflow', 'visible');
    const box = (await button.boundingBox())!;
    expect(box.width).toBeGreaterThanOrEqual(48);
    expect(box.height).toBeGreaterThanOrEqual(56);
  }
});

test('busy FormField retains help and caller accessible description', async ({page}) => {
  await page.setContent(render(h('div', null,
    h('p', {id: 'context'}, 'Address context'),
    h(FormField, {
      id: 'landmark', label: 'Landmark', help: 'Near a familiar place',
      busy: true, required: true, 'aria-describedby': 'context',
    }),
  )));
  const input = page.getByLabel('Landmark');
  await expect(input).toHaveAccessibleDescription('Address context Near a familiar place');
  await expect(input).toHaveAttribute('required', '');
  await expect(input).toHaveAttribute('aria-busy', 'true');
  await input.fill('School gate');
  await expect(input).toHaveValue('School gate');
  await input.focus();
  await expect(input).toHaveCSS('outline-style', 'solid');
  expect((await input.boundingBox())!.height).toBeGreaterThanOrEqual(48);
});

test('FormField error, loading, readonly, disabled, and caller invalid semantics are deterministic', async ({page}) => {
  await page.setContent(render(h('div', null,
    h(FormField, {id: 'error', label: 'Error field', errorMessage: 'Add a landmark', defaultValue: 'Gate', busy: true, loadingMessage: 'Checking…'}),
    h(FormField, {id: 'loading', label: 'Loading field', busy: true, loadingMessage: 'Checking…', defaultValue: 'School'}),
    h(FormField, {id: 'readonly', label: 'Read-only field', readOnly: true, defaultValue: 'Kept'}),
    h(FormField, {id: 'disabled', label: 'Disabled field', disabled: true, defaultValue: 'Kept'}),
    h(FormField, {id: 'invalid', label: 'Caller invalid field', 'aria-invalid': 'grammar'}),
  )));
  await expect(page.getByLabel('Error field')).toHaveAccessibleDescription('Add a landmark');
  await expect(page.getByLabel('Error field')).toHaveAttribute('aria-invalid', 'true');
  await expect(page.getByLabel('Error field')).toHaveValue('Gate');
  await expect(page.getByLabel('Loading field')).toHaveAccessibleDescription('Checking…');
  await expect(page.getByLabel('Loading field')).toHaveValue('School');
  await expect(page.getByLabel('Read-only field')).not.toBeEditable();
  await expect(page.getByLabel('Disabled field')).toBeDisabled();
  await expect(page.getByLabel('Caller invalid field')).toHaveAttribute('aria-invalid', 'grammar');
});

test('Feedback roles and busy Retry are meaningful', async ({page}) => {
  await page.setContent(render(h('div', null,
    h(Notice, {tone: 'success', children: 'Address saved'}),
    h(Loading, {label: 'Checking availability…'}),
    h(Empty, {title: 'No results', explanation: 'Try another search'}),
    h(Retry, {message: 'Could not load', busy: true, onRetry: () => {}}),
  )));
  await expect(page.getByText('Address saved')).toHaveAttribute('role', 'status');
  await expect(page.getByText('Checking availability…')).toHaveAttribute('role', 'status');
  await expect(page.getByRole('heading', {name: 'No results'})).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Could not load');
  await expect(page.getByRole('button', {name: 'Trying again…'})).toBeDisabled();
});

test('PriceBreakdown renders only the supplied authoritative amounts', async ({page}) => {
  await page.setContent(render(h(PriceBreakdown, {
    subtotal: '145.00', deliveryFee: '37.50', total: '182.50',
    format: (value: string | number) => `INR ${value}`,
  })));
  const summary = page.getByRole('region', {name: 'Current order quote'});
  await expect(summary).toContainText('INR 145.00');
  await expect(summary).toContainText('INR 37.50');
  await expect(summary).toContainText('INR 182.50');
  await expect(summary).not.toContainText('20.00');
});

for (const width of [320, 360, 390]) {
  test(`localized large Button labels reflow at ${width}`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    const labels = [
      'Check delivery availability for this address and continue',
      'इस पते पर डिलीवरी की उपलब्धता जाँचें और आगे बढ़ें',
      'या पत्त्यावर वितरण उपलब्ध आहे का ते तपासा आणि पुढे जा',
    ];
    await page.setContent(render(h('div', {style: {padding: 16, display: 'grid', gap: 16, fontSize: '200%'}},
      ...labels.map((label, index) => h(Button, {key: label, lang: ['en', 'hi', 'mr'][index]}, label)),
    )));
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    for (const button of await page.getByRole('button').all()) {
      expect((await button.boundingBox())!.height).toBeGreaterThanOrEqual(56);
      expect(await button.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    }
  });
}
