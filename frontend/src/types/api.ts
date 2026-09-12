/** Shapes returned by the FastAPI backend on error responses. */

export interface ValidationErrorDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/** FastAPI's `HTTPException` body, or its 422 validation payload. */
export interface ApiErrorBody {
  detail?: string | ValidationErrorDetail[];
}

/** Value types accepted as URL query-string parameters. */
export type QueryValue = string | number | boolean | null | undefined;

export type QueryParams = Record<string, QueryValue | QueryValue[]>;
