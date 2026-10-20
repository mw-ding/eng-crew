import http from "node:http"; import fs from "node:fs"; import path from "node:path";
import { chromium } from "playwright-core";
import els from "./scene.mjs";
const ROOT = process.cwd();
const srv = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split("?")[0]);
  if (p === "/") { res.setHeader("content-type", "text/html"); return res.end(`<!doctype html><html><body><script>window.EXCALIDRAW_ASSET_PATH="/node_modules/@excalidraw/excalidraw/dist/prod/";</script><script src="/bundle.js"></script></body></html>`); }
  const f = path.join(ROOT, p);
  if (!fs.existsSync(f)) { console.error("404", p); res.statusCode = 404; return res.end(); }
  const ext = path.extname(f);
  res.setHeader("content-type", { ".js": "text/javascript", ".woff2": "font/woff2", ".ttf": "font/ttf" }[ext] || "application/octet-stream");
  fs.createReadStream(f).pipe(res);
}).listen(0);
const port = srv.address().port;
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox"] });
const page = await browser.newPage();
page.on("console", (m) => console.log("[page]", m.text()));
page.on("pageerror", (e) => console.log("[pageerror]", e.message));
await page.goto(`http://localhost:${port}/`);
await page.waitForFunction(() => window.EX);
const out = await page.evaluate(async (skel) => {
  const { convertToExcalidrawElements, exportToBlob } = window.EX;
  const elements = convertToExcalidrawElements(skel, { regenerateIds: false });
  const appState = { exportBackground: true, viewBackgroundColor: "#ffffff", exportWithDarkMode: false };
  const blob = await exportToBlob({ elements, appState, files: {}, mimeType: "image/png", exportPadding: 40, getDimensions: (w, h) => ({ width: w * 1.5, height: h * 1.5, scale: 1.5 }) });
  const buf = new Uint8Array(await blob.arrayBuffer());
  let s = ""; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return { elements, png: btoa(s) };
}, els);
const scene = { type: "excalidraw", version: 2, source: "https://excalidraw.com", elements: out.elements, appState: { viewBackgroundColor: "#ffffff", gridSize: null }, files: {} };
fs.writeFileSync("../eng-crew-flow.excalidraw", JSON.stringify(scene, null, 2));
fs.writeFileSync("../eng-crew-flow.png", Buffer.from(out.png, "base64"));
await browser.close(); srv.close();
console.log("ok", out.elements.length);
