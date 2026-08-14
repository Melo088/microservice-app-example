output "vm_public_ip" {
  description = "IP pública de la VM."
  value       = azurerm_public_ip.main.ip_address
}

output "ssh_command" {
  description = "Comando para conectarse por SSH a la VM."
  value       = "ssh -i ~/.ssh/microservice-app-example-azure ${var.admin_username}@${azurerm_public_ip.main.ip_address}"
}

output "frontend_url" {
  description = "URL pública del frontend una vez Ansible haya desplegado la app."
  value       = "http://${azurerm_public_ip.main.ip_address}:8080"
}

output "zipkin_url" {
  description = "URL pública de Zipkin una vez Ansible haya desplegado la app."
  value       = "http://${azurerm_public_ip.main.ip_address}:9411/zipkin/"
}
