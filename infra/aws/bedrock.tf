# Receipt OCR backend (CLOUDAPPG5-95). Bedrock is the chosen reader after the
# scripts/ocr_compare trial; Textract stays available as a fallback.

variable "ocr_backend" {
  description = "Which reader the API uses for receipts: bedrock or textract."
  type        = string
  default     = "bedrock"
  validation {
    condition     = contains(["bedrock", "textract"], var.ocr_backend)
    error_message = "ocr_backend must be bedrock or textract."
  }
}

variable "bedrock_model_id" {
  description = "Bedrock model ID or inference profile ID, copied from the Bedrock console. The model must be enabled for the account."
  type        = string
  default     = ""
}

variable "bedrock_region" {
  description = "Region to call Bedrock in. Empty means the API's AWS_REGION."
  type        = string
  default     = ""
}
