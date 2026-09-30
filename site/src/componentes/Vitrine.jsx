import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { TELAS } from "../conteudo.js";
import "./Vitrine.css";

// Telas reais da interface do terminal, com dados fictícios.
export default function Vitrine() {
  const [ativa, setAtiva] = useState(TELAS[2].id);
  const reduzir = useReducedMotion();
  const tela = TELAS.find((t) => t.id === ativa);

  return (
    <section className="secao vitrine" id="por-dentro">
      <div className="largura">
        <h2 className="secao-titulo">Um roteiro claro, na tela do seu computador</h2>
        <p className="secao-sub">
          No terminal, o Expeditto tem uma interface própria. Pelo chat, o seu assistente de IA segue o mesmo roteiro.
        </p>

        <div className="vitrine-abas" role="tablist" aria-label="Telas do Expeditto">
          {TELAS.map((t) => (
            <button
              key={t.id}
              role="tab"
              id={`tela-${t.id}`}
              aria-selected={t.id === ativa}
              aria-controls="vitrine-painel"
              onClick={() => setAtiva(t.id)}
            >
              {t.rotulo}
            </button>
          ))}
        </div>

        <figure className="vitrine-quadro" id="vitrine-painel" role="tabpanel" aria-labelledby={`tela-${ativa}`}>
          <div className="vitrine-imagem">
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.img
                key={tela.id}
                src={tela.imagem}
                alt={`Tela "${tela.rotulo}" do Expeditto no terminal`}
                width="2044"
                height="1438"
                loading="lazy"
                initial={reduzir ? false : { opacity: 0, scale: 0.985 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={reduzir ? undefined : { opacity: 0 }}
                transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
              />
            </AnimatePresence>
          </div>
          <figcaption>{tela.texto}</figcaption>
        </figure>
      </div>
    </section>
  );
}
