import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

async function render() {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request("http://localhost/", {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

const frontendRoot = new URL("../", import.meta.url);

test("server-renders the safe-rent product entry screen", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>안심계약 레이더<\/title>/i);
  assert.match(html, /주소와 보증금으로 시작하는/);
  assert.match(html, /계약할 매물을 알려주세요/);
  assert.match(html, /DIVE 2026/);
  assert.doesNotMatch(html, /codex-preview|Building your site/);
});

test("keeps the AI similar-case screen connected and clearly limited", async () => {
  const [page, component, sampleData] = await Promise.all([
    readFile(new URL("app/page.tsx", frontendRoot), "utf8"),
    readFile(
      new URL("app/components/SimilarCaseCard.tsx", frontendRoot),
      "utf8",
    ),
    readFile(
      new URL("app/data/similarCasesSample.ts", frontendRoot),
      "utf8",
    ),
  ]);

  assert.match(page, /<SimilarCaseCard guaranteeStatus=\{guaranteeStatus\}/);
  assert.match(component, /비슷한 상담사례를 쉬운 말로 설명합니다/);
  assert.match(component, /유사사례는 결과를 예측하지 않습니다/);
  assert.match(component, /aria-pressed=\{isSelected\}/);
  assert.match(sampleData, /status === "enrolled"/);
  assert.match(sampleData, /kind: "difference"/);
  assert.match(sampleData, /AI 상담사례 API 연동 전 샘플/);
});
