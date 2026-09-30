import { OpenAiLogo, TerminalWindow } from "@phosphor-icons/react";
import { APPS } from "../conteudo.js";
import "./Apps.css";

function Logo({ logo }) {
  if (logo === "openai") return <OpenAiLogo size={22} weight="fill" />;
  if (logo === "terminal") return <TerminalWindow size={22} weight="duotone" />;
  return <img src={logo} alt="" width="22" height="22" />;
}

export default function Apps() {
  return (
    <section className="secao apps">
      <div className="largura apps-grade">
        <div>
          <h2 className="secao-titulo">Converse como falaria com um colega</h2>
          <p className="secao-sub">
            Escreva “me ajuda com meu relatório do semestre” no seu assistente de IA. O instalador conecta o Expeditto
            aos apps que você já tem.
          </p>
        </div>
        <ul className="apps-lista" aria-label="Onde o Expeditto funciona">
          {APPS.map((app) => (
            <li key={app.nome}>
              <Logo logo={app.logo} />
              {app.nome}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
