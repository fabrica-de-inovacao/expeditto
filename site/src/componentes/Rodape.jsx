import { REPOSITORIO } from "../conteudo.js";
import "./Rodape.css";

export default function Rodape() {
  return (
    <footer className="rodape">
      <div className="largura rodape-linha">
        <p>Expeditto é uma ferramenta independente e não oficial, sem vínculo com o IFMA ou com o SUAP.</p>
        <p className="rodape-links">
          <a href={REPOSITORIO}>Código-fonte</a>
          <a href={`${REPOSITORIO}/blob/main/LICENSE`}>Licença AGPL-3.0</a>
        </p>
      </div>
    </footer>
  );
}
