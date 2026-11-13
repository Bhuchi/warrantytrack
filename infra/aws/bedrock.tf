# Receipt OCR (CLOUDAPPG5-95): a Claude model on Amazon Bedrock reads each
# uploaded receipt. Chosen after the scripts/ocr_compare trial.

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
