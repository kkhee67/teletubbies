import { adaptAnalyzeResponse, adaptPropertySearchResponse } from "./adapters";
import type {
  AnalyzeRequestPayload,
  ApiClientOptions,
  PropertySearchItem,
  SearchAndAnalyzeInput,
  SearchAndAnalyzeResult,
} from "./types";

export const DEFAULT_API_BASE_URL = "/api/backend";

function getConfiguredApiBaseUrl(): string | undefined {
  const nextPublicValue = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (nextPublicValue) return nextPublicValue;

  const viteEnv = import.meta.env as Record<string, string | undefined> | undefined;
  return (
    viteEnv?.VITE_API_BASE_URL?.trim() ||
    viteEnv?.NEXT_PUBLIC_API_BASE_URL?.trim()
  );
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string | null;
  readonly details: unknown;

  constructor(
    message: string,
    options: {
      status?: number | null;
      code?: string | null;
      details?: unknown;
      cause?: unknown;
    } = {},
  ) {
    super(message, { cause: options.cause });
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.code = options.code ?? null;
    this.details = options.details ?? null;
  }
}

export function getApiBaseUrl(explicitBaseUrl?: string): string {
  const configured =
    explicitBaseUrl?.trim() ||
    getConfiguredApiBaseUrl() ||
    DEFAULT_API_BASE_URL;
  return configured.replace(/\/+$/, "");
}

function errorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const record = payload as Record<string, unknown>;
    const detail = record.detail ?? record.message ?? record.error;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
  }
  return `API 요청에 실패했습니다. (${status})`;
}

function errorCode(payload: unknown): string | null {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  const code = (payload as Record<string, unknown>).code;
  return typeof code === "string" && code.trim() ? code.trim() : null;
}

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function requestJson(
  path: string,
  init: RequestInit,
  options: ApiClientOptions,
): Promise<unknown> {
  const fetcher = options.fetcher ?? globalThis.fetch;
  if (!fetcher) {
    throw new ApiError("이 환경에서는 API 요청을 보낼 수 없습니다.", {
      code: "FETCH_UNAVAILABLE",
    });
  }

  let response: Response;
  try {
    response = await fetcher(`${getApiBaseUrl(options.baseUrl)}${path}`, {
      ...init,
      signal: options.signal,
      headers: {
        Accept: "application/json",
        ...init.headers,
      },
    });
  } catch (cause) {
    if (cause instanceof Error && cause.name === "AbortError") {
      throw cause;
    }
    throw new ApiError("백엔드 API에 연결하지 못했습니다.", {
      code: "NETWORK_ERROR",
      cause,
    });
  }

  const payload = await readResponseBody(response);
  if (!response.ok) {
    throw new ApiError(errorMessage(payload, response.status), {
      status: response.status,
      code: errorCode(payload),
      details: payload,
    });
  }

  return payload;
}

export async function searchProperties(
  address: string,
  options: ApiClientOptions = {},
): Promise<PropertySearchItem[]> {
  const query = address.trim();
  if (!query) {
    throw new ApiError("검색할 주소를 입력해 주세요.", {
      code: "INVALID_ADDRESS",
    });
  }

  const payload = await requestJson(
    `/properties/search?q=${encodeURIComponent(query)}`,
    { method: "GET" },
    options,
  );
  return adaptPropertySearchResponse(payload);
}

export async function analyzeProperty(
  request: AnalyzeRequestPayload,
  options: ApiClientOptions = {},
): Promise<unknown> {
  const hasPropertyId = Boolean(request.property_id?.trim());
  const hasAddress = Boolean(request.address_query.trim());
  if (
    (!hasPropertyId && !hasAddress) ||
    !Number.isFinite(request.planned_deposit) ||
    request.planned_deposit <= 0
  ) {
    throw new ApiError("주소 또는 매물 ID와 0원보다 큰 보증금이 필요합니다.", {
      code: "INVALID_ANALYZE_REQUEST",
    });
  }

  return requestJson(
    "/analyze",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
    options,
  );
}

export async function searchAndAnalyze(
  input: SearchAndAnalyzeInput,
  options: ApiClientOptions = {},
): Promise<SearchAndAnalyzeResult> {
  const address = input.address.trim();
  if (!address || !Number.isFinite(input.plannedDeposit)) {
    throw new ApiError("주소와 올바른 보증금을 입력해 주세요.", {
      code: "INVALID_INPUT",
    });
  }

  const searchItems = await searchProperties(address, options);
  const searchItem = searchItems[0];
  const addressOnlyItem: PropertySearchItem = {
    propertyId: "ADDRESS_ONLY",
    addressDisplay: address,
    district: null,
    housingType: null,
    referenceValue: null,
    guaranteeStatus: null,
  };
  const selectedItem = searchItem ?? addressOnlyItem;

  const request: AnalyzeRequestPayload = {
    address_query: address,
    planned_deposit: input.plannedDeposit,
    monthly_rent: input.monthlyRent ?? 0,
    user_note: input.userNote ?? "",
  };
  if (searchItem) {
    request.property_id = searchItem.propertyId;
  }
  if (input.userCorrections) {
    request.user_corrections = input.userCorrections;
  }

  const rawAnalysisResponse = await analyzeProperty(request, options);
  const analysis = adaptAnalyzeResponse(rawAnalysisResponse);
  const propertyId = analysis.propertySummary.propertyId ?? selectedItem.propertyId;
  return {
    propertyId,
    searchItem: {
      ...selectedItem,
      propertyId,
      addressDisplay: selectedItem.addressDisplay ?? address,
    },
    analysis,
    rawAnalysisResponse,
  };
}
