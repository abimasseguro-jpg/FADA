# Configuração do Resource Controller

O arquivo `resource_controller.example.json` é somente um exemplo estrutural e
permanece em modo `disabled`. Frequências, níveis, temperaturas e reservas não
são defaults de produção e precisam ser autorizados separadamente para cada
máquina hospedeira.

O carregador rejeita versão desconhecida, campo extra, nível duplicado e unidade
ambígua. O contrato formal está em
`schemas/v1/machine_resource_config.json`.
