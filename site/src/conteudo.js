// Textos e dados da página. Mantidos aqui para editar sem mexer nos componentes.

export const REPOSITORIO = "https://github.com/vnschneider/expeditto";

const origem = typeof window !== "undefined" && window.location.origin.startsWith("http")
  ? window.location.origin
  : "https://expeditto.fabitz.com.br";

export const INSTALACAO = {
  windows: {
    rotulo: "Windows",
    comando: `powershell -ExecutionPolicy ByPass -c "irm ${origem}/install.ps1 | iex"`,
    dica: "Abra o PowerShell pelo menu Iniciar, cole o comando e tecle Enter.",
  },
  unix: {
    rotulo: "macOS e Linux",
    comando: `curl -LsSf ${origem}/install.sh | sh`,
    dica: "Abra o Terminal, cole o comando e tecle Enter. Não pede senha de administrador.",
  },
};

export const TELAS = [
  {
    id: "inicio",
    rotulo: "Seus semestres",
    imagem: "/telas/inicio.webp",
    texto: "Cada semestre com a situação no SUAP, quantos comprovantes já estão no acervo e o próximo passo.",
  },
  {
    id: "coleta",
    rotulo: "Coleta",
    imagem: "/telas/coleta.webp",
    texto: "A busca no SUAP acontece por etapas, com uma barra para cada uma. Leva de 2 a 8 minutos.",
  },
  {
    id: "pendencias",
    rotulo: "Pendências",
    imagem: "/telas/pendencias.webp",
    texto: "O que ficou sem comprovante vem agrupado. Você marca os itens e decide de uma vez.",
  },
  {
    id: "anexos",
    rotulo: "Anexos",
    imagem: "/telas/anexos.webp",
    texto: "Um PDF por tópico, com capa e índice, sempre abaixo do limite de 10 MB do SUAP.",
  },
];

export const PASSOS = [
  {
    titulo: "Coletar",
    texto: "Diários, estágios, TCCs, bancas, portarias, projetos e o seu Lattes, direto do SUAP.",
    icone: "coletar",
  },
  {
    titulo: "Decidir",
    texto: "Você resolve as pendências: manter, deixar de fora ou justificar com as suas palavras.",
    icone: "decidir",
  },
  {
    titulo: "Escrever",
    texto: "Um relato por tópico, com os fatos e as contagens certas, mais o PDF de comprovantes.",
    icone: "escrever",
  },
  {
    titulo: "Salvar",
    texto: "Com o seu OK, tudo vai para o formulário do RIT como rascunho. A entrega é sua.",
    icone: "salvar",
  },
];

export const APPS = [
  { nome: "Claude Desktop", logo: "/logos/claude.svg" },
  { nome: "Claude Code", logo: "/logos/claude.svg" },
  { nome: "Codex", logo: "openai" },
  { nome: "Gemini CLI", logo: "/logos/gemini.svg" },
  { nome: "Antigravity", logo: "/logos/gemini.svg" },
  { nome: "Terminal", logo: "terminal" },
];

export const GARANTIAS = [
  {
    titulo: "Não vê sua senha",
    texto: "Você entra no SUAP numa janela do navegador. Só a sessão fica guardada, no cofre de senhas do sistema.",
    icone: "senha",
  },
  {
    titulo: "Não entrega o RIT",
    texto: "Ele salva como rascunho e mostra os links. Quem submete para avaliação é você.",
    icone: "entrega",
  },
  {
    titulo: "Não manda dados para fora",
    texto: "O acervo fica numa pasta sua. O código é aberto e pode ser auditado por qualquer pessoa.",
    icone: "dados",
  },
];

export const PERGUNTAS = [
  {
    pergunta: "Preciso pagar?",
    resposta:
      "Não. O Expeditto é gratuito e de código aberto (licença AGPL-3.0). Para conversar com ele pelo chat, você usa o assistente de IA que já tem, como o Claude.",
  },
  {
    pergunta: "É uma ferramenta oficial do IFMA?",
    resposta:
      "Não. É uma ferramenta independente, sem vínculo com o IFMA ou com o SUAP. Ela usa as mesmas telas que você usa no navegador, com a sua sessão.",
  },
  {
    pergunta: "Onde ficam os meus comprovantes?",
    resposta:
      "Numa pasta no seu computador (expeditto, dentro da sua pasta de usuário). Nada é enviado para servidores do Expeditto.",
  },
  {
    pergunta: "E se eu não usar assistente de IA?",
    resposta:
      "Dá para fazer tudo pelo terminal: rode expeditto e siga as telas. O assistente só deixa a conversa mais natural e os relatos mais caprichados.",
  },
  {
    pergunta: "Posso desfazer a instalação?",
    resposta:
      "Sim. O comando expeditto desinstalar tira o Expeditto dos seus apps. Seus dados só são apagados se você pedir.",
  },
];
