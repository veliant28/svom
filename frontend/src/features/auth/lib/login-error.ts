import { isApiRequestError } from "@/shared/api/http-client";

type LoginErrorView = {
  translationKey: string;
  values?: Record<string, string | number>;
};

export function resolveLoginError(error: unknown): LoginErrorView {
  if (isApiRequestError(error)) {
    if (error.status === 400 || error.status === 401) {
      return { translationKey: "errors.invalidCredentials" };
    }

    if (error.status === 404) {
      return {
        translationKey: "errors.endpointNotFound",
        values: { url: error.url },
      };
    }

    if (error.isNetworkError) {
      return {
        translationKey: "errors.network",
        values: { url: error.url },
      };
    }

    return {
      translationKey: "errors.server",
      values: {
        status: error.status ?? "unknown",
        url: error.url,
      },
    };
  }

  return { translationKey: "errors.unknown" };
}
