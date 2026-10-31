variable "environment" {
  description = "Target deployment environment (e.g. dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Name of the Azure Resource Group"
  type        = string
  default     = "rg-docling-platform-dev"
}

variable "cluster_name" {
  description = "Name of the managed AKS cluster"
  type        = string
  default     = "aks-docling-platform-dev"
}

variable "dns_prefix" {
  description = "DNS prefix for the AKS cluster"
  type        = string
  default     = "docling-platform"
}

variable "node_count" {
  description = "Initial number of worker nodes in the system pool"
  type        = number
  default     = 2
}

variable "vm_size" {
  description = "Azure VM size for the CPU node pool (Standard_D2s_v5 or Standard_B2s for budget control)"
  type        = string
  default     = "Standard_D2s_v5"
}

variable "vnet_address_space" {
  description = "Virtual Network CIDR block"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}

variable "aks_subnet_address_prefix" {
  description = "Subnet CIDR block dedicated to AKS nodes and pods"
  type        = list(string)
  default     = ["10.0.1.0/24"]
}

variable "tags" {
  description = "Resource tags applied to all provisioned infrastructure"
  type        = map(string)
  default = {
    Project     = "Docling-Platform"
    ManagedBy   = "Terraform"
    Environment = "dev"
    Workload    = "Document-Intelligence"
  }
}

