# Incidente operacional — contexto de raiz entre projetos

## Falha observada

O primeiro encaminhamento de um aprendizado FADA ao Sentinela tentou criar um
arquivo e executar `sentinela_ai.py` com caminhos relativos do MVHSN enquanto o
diretório corrente era o projeto FADA. A cópia e a chamada falharam; os testes,
que pertenciam corretamente ao FADA, foram executados e passaram.

## Causa e fronteira causal

Causa demonstrada pelas mensagens `No such file or directory`: mistura entre a
raiz operacional do comando e caminhos relativos pertencentes ao projeto irmão.
Não houve evidência de alteração parcial no Sentinela ou na campanha.

## Generalização e solução

Operações entre projetos irmãos devem resolver e validar separadamente três
elementos: raiz da ferramenta, origem do artefato e destino. Usar caminhos
absolutos para a transferência e executar a ferramenta com `cwd` igual à raiz que
ela governa. Uma falha de encaminhamento deve ser registrada antes da repetição.

## Estado

`demonstrated`; correção operacional aplicada no segundo encaminhamento.

