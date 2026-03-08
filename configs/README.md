# Configs

Каталог для конфигурационного слоя коробочной версии.

Здесь должны храниться:

- branding/theme
- feature flags
- env templates
- tenant/client presets
- integration settings templates

Правило архитектуры:

- Configs меняют поведение без переписывания core
- Client-specific logic не хранится в configs, если это уже отдельная интеграция или кастомный workflow
- Secrets не хранятся в репозитории
