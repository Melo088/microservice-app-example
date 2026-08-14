variable "project_name" {
  description = "Prefijo para nombrar todos los recursos de Azure."
  type        = string
  default     = "microservice-app"
}

variable "location" {
  description = "mexicocentral. eastus se descartó porque una política de la suscripción (Allowed resource deployment regions) restringe el despliegue a southcentralus, brazilsouth, westus3, eastus2 y mexicocentral. De esa lista, mexicocentral es la más cercana a Colombia y sí tiene Standard_B2s disponible."
  type        = string
  default     = "mexicocentral"
}

variable "vm_size" {
  description = "Tamaño de la VM. Standard_B2s (2 vCPU/4GB)"
  type        = string
  default     = "Standard_B2s"
}

variable "admin_username" {
  description = "Usuario administrador de la VM."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key_path" {
  description = "Ruta local a la llave pública SSH que se inyecta en la VM."
  type        = string
  default     = "~/.ssh/microservice-app-example-azure.pub"
}

variable "allowed_ssh_cidr" {
  description = "Rango de IPs permitido para SSH (puerto 22)"
  type        = string
  default     = "0.0.0.0/0"
}
