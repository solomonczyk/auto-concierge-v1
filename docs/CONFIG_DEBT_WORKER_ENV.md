# Tech Debt: Worker Redis Config Coupling

## Current issue

- worker не использует Redis напрямую
- но REDIS_HOST всё равно обязателен из-за общих settings

## Risk

- лишняя зависимость в конфиге
- вводит в заблуждение при сопровождении
- мешает честно отделить worker runtime от bot/runtime/websocket parts

## Target fix

- сделать settings менее жёсткими
- Redis-конфиг должен быть required только там, где реально нужен
- worker должен стартовать без Redis-переменных
