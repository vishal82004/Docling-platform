output "resource_group_name" {
  description = "The name of the provisioned Azure Resource Group"
  value       = azurerm_resource_group.rg.name
}

output "kubernetes_cluster_name" {
  description = "The name of the managed AKS cluster"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "kubernetes_cluster_id" {
  description = "Resource ID of the managed AKS cluster"
  value       = azurerm_kubernetes_cluster.aks.id
}

output "cluster_identity_principal_id" {
  description = "The Principal ID of the AKS system-assigned managed identity"
  value       = azurerm_kubernetes_cluster.aks.identity[0].principal_id
}

output "get_credentials_command" {
  description = "Azure CLI command to configure kubectl with the cluster context"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.rg.name} --name ${azurerm_kubernetes_cluster.aks.name}"
}

