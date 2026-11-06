// Puerta de F3: enlace del viewer demo abierto MIENTRAS el job corre.
//
//   VIEWER_DIR=../lamula-webviewer node jobs/e2e/viewer_f3.mjs <result_token> <dir-de-salida>
//
// Supone el viewer en http://127.0.0.1:3100 con NUXT_JOBS_API_URL, NUXT_JOBS_INTERNAL_KEY, NUXT_PG_*,
// NUXT_PUBLIC_DEMO_JOB=true y NUXT_PUBLIC_R2_BASE_URL apuntando al bucket de rasters, más un job en marcha
// (jobs/e2e/lib.py: alta). Registra cada cambio de la pantalla de estado, el momento de la redirección al
// visor, que el raster cargue, que no haya viento/rayos/feedback y los frames conocidos; guarda una captura.
import { createRequire } from 'node:module'
const require = createRequire(`${process.env.VIEWER_DIR ?? '../lamula-webviewer'}/package.json`.replace(/^(?!\/)/, process.cwd() + '/'))
const { chromium } = require('@playwright/test')
const [token, out] = process.argv.slice(2)
const t0 = Date.now()
const log = (m) => console.log(`+${Math.round((Date.now() - t0) / 1000)}s ${m}`)
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
const bad = []
page.on('response', (r) => { if (r.status() >= 400) bad.push(`${r.status()} ${r.url().replace('http://127.0.0.1:3100', '')}`) })
await page.goto(`http://127.0.0.1:3100/j/${token}`)
let last = ''
let redirected = false
while (Date.now() - t0 < 14 * 60_000) {
  const url = new URL(page.url()).pathname
  if (!url.startsWith('/j/')) { redirected = true; log(`redirigido a ${url}`); break }
  const txt = (await page.getByTestId('job-status').textContent().catch(() => '?'))?.trim()
  if (txt !== last) { log(`estado: ${txt}`); last = txt }
  await page.waitForTimeout(2000)
}
if (!redirected) { log('FALLO: nunca redirigió'); await page.screenshot({ path: `${out}/f3-sin-redireccion.png` }); process.exit(1) }
await page.waitForSelector('[data-testid="timeline"]', { timeout: 60_000 })
const cargado = await page.waitForSelector('[data-raster-loaded="true"]', { timeout: 60_000 }).then(() => true, () => false)
log(`raster cargado en el mapa: ${cargado}`)
await page.waitForTimeout(2000)
log(`pastilla feedback: ${await page.getByTestId('feedback-pill').count()}`)
await page.screenshot({ path: `${out}/f3-visor.png` })
log(`pastilla viento: ${await page.getByTestId('layer-toggle-wind-pill').count()}  rayos: ${await page.getByTestId('layer-toggle-lightning-pill').count()}`)
log(`pastilla satélite/celdas presentes: ${await page.getByTestId('layer-toggle-cells-pill').count()}`)
// ¿cuántos frames conoce el visor ahora, y crecen mientras el job sigue?
const frames = async () => (await page.evaluate(async () => {
  const p = location.pathname.split('/').filter(Boolean).filter(x => x !== 'es' && x !== 'en')
  const r = await fetch(`/api/rasters/times?site=${p[0]}&product=${p[1]}&day=2017-09-10`)
  return r.ok ? (await r.json()).length : -r.status
}))
log(`frames del producto abierto el 2017-09-10: ${await frames()}`)
// La sesión sigue abierta, SIN recargar: ¿aparecen los productos que el job publica después?
const estado = () => page.evaluate(async (t) => (await (await fetch(`/api/job/${t}`)).json()).state, token)
const hora = async () => (await page.locator('text=/\\d\\d:\\d\\d:\\d\\d GMT/').first().textContent().catch(() => '?'))?.trim()
let prev = ''
let estadoJob = await estado()
let maxFrames = await frames()
while (Date.now() - t0 < 25 * 60_000) {
  const n = await frames()
  maxFrames = Math.max(maxFrames, n)
  const linea = `job=${estadoJob} frames=${n} visor muestra ${await hora()} en ${new URL(page.url()).pathname}`
  if (linea !== prev) { log(linea); prev = linea }
  if (['ready', 'failed', 'cancelled', 'expired'].includes(estadoJob)) break
  await page.waitForTimeout(10_000)
  estadoJob = await estado()
}
await page.screenshot({ path: `${out}/f3-visor-final.png` })
log(`frames máximos vistos en la sesión: ${maxFrames}`)
log(`respuestas >=400: ${JSON.stringify(bad)}`)
await browser.close()
