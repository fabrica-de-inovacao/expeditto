# Itens do Lattes

O Lattes é autodeclaração: não é comprovante. O Expeditto compara o Lattes do ano com o que achou no SUAP e
mostra o que não tem comprovante.

O Lattes só informa o ano. Para saber o semestre, o Expeditto consulta bases públicas de publicações
(Crossref e OpenAlex) pelo DOI ou pelo título, e traz o tipo (artigo em periódico, artigo em anais, capítulo
de livro...), o veículo (revista, evento, livro), a data completa e o link do DOI. Só consulta títulos que já
são públicos no Lattes. Coletas antigas podem não ter esses dados: use `completar_lattes`.

## Como decidir

- **`sugestao` diz "parece ser deste semestre":** pergunte se o docente tem o comprovante (PDF do artigo,
  certificado do evento, carta de aceite). Se tiver, ele coloca na pasta de entrada, no tópico indicado, e
  a decisão é `manter`.
- **"parece ser de outro semestre":** a decisão costuma ser `ignorar` (deixar de fora). Confirme com ele.
- **Sem data:** mostre o título, o tipo e o veículo, e pergunte em que mês foi publicado ou apresentado.

Apresente em lotes pela sugestão ("estes 3 parecem deste semestre, estes 5 de outro"), não item a item.
