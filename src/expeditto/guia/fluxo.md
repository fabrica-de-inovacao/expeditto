# Fluxo do RIT

A porta de entrada é sempre `preparar_rit` (com o semestre, se o docente disser qual). A resposta diz em
que etapa o semestre está, o que dizer ao docente (`mensagem`) e qual ferramenta chamar (`proximo`).
Depois de cada etapa concluída, chame `preparar_rit` de novo.

| Etapa | O que acontece | Ferramentas |
|---|---|---|
| login | O docente entra no SUAP numa janela do navegador (CAPTCHA/Gov.br). | `login`, `aguardar_tarefa` |
| escolher semestre | Mostre os RITs a preencher e pergunte qual. | `preparar_rit` |
| coletar | Busca diários, estágios, TCCs, bancas, portarias, projetos e o Lattes. 2 a 8 minutos. | `coletar_semestre`, `aguardar_tarefa` |
| pendências | O docente decide o que ficou sem comprovante ou em dúvida. | `detalhar_pendencia`, `resolver_pendencia`, `completar_lattes` |
| anexos | Um PDF por tópico, até 10 MB. | `montar_anexos`, `pasta_entrada` |
| relatos | Um texto por tópico, a partir dos fatos. | `contexto_topico`, `salvar_texto` |
| alterações | Texto com as justificativas do docente. | `gerar_alteracoes` |
| salvar | Mostre a prévia e peça confirmação explícita. | `previa_preenchimento`, `salvar_no_suap` |

## Progresso de tarefas longas

`coletar_semestre` e `login` devolvem um `tarefa_id`. Chame `aguardar_tarefa` em sequência: cada chamada
volta em cerca de 10 segundos (ou antes, quando muda de etapa). A cada resposta, mostre a linha
`progresso` (a barra) e, se útil, o `detalhe`. Não fique em silêncio: uma frase curta por atualização basta.

## Conversa

- Comece dizendo o que vai fazer e quanto tempo leva.
- Nas pendências, apresente um grupo por vez com a `pergunta_sugerida`. Se o docente tiver dúvida sobre um
  item, use `detalhar_pendencia` e mostre os links para ele conferir.
- Se ele pedir para ver algo, use `abrir_no_navegador` com o link do item.
- Ao final, mostre o `cartao` exatamente como veio e lembre que a entrega é dele, no SUAP.
