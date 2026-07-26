/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  API_BASE_URL?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const API_PROXY_PREFIX = "/api/backend";
const DEFAULT_BACKEND_API_BASE_URL = "https://teletubbies-kimf.onrender.com";

function createBackendUrl(requestUrl: URL, apiBaseUrl: string) {
  const targetUrl = new URL(apiBaseUrl);
  const targetBasePath = targetUrl.pathname.replace(/\/+$/, "");
  const requestPath = requestUrl.pathname.slice(API_PROXY_PREFIX.length) || "/";
  const normalizedRequestPath = requestPath.startsWith("/")
    ? requestPath
    : `/${requestPath}`;

  targetUrl.pathname = `${targetBasePath}${normalizedRequestPath}`;
  targetUrl.search = requestUrl.search;
  return targetUrl;
}

async function proxyBackendApi(request: Request, env: Env) {
  const requestUrl = new URL(request.url);
  const apiBaseUrl = env.API_BASE_URL?.trim() || DEFAULT_BACKEND_API_BASE_URL;
  const targetUrl = createBackendUrl(requestUrl, apiBaseUrl);
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("origin");

  try {
    const response = await fetch(
      new Request(targetUrl, {
        method: request.method,
        headers,
        body:
          request.method === "GET" || request.method === "HEAD"
            ? undefined
            : request.body,
        redirect: "manual",
      }),
    );

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    });
  } catch {
    return Response.json(
      {
        detail: "백엔드 API에 연결할 수 없습니다.",
        code: "BACKEND_PROXY_ERROR",
        extra: {},
      },
      { status: 502 },
    );
  }
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (
      url.pathname === API_PROXY_PREFIX ||
      url.pathname.startsWith(`${API_PROXY_PREFIX}/`)
    ) {
      return proxyBackendApi(request, env);
    }

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
