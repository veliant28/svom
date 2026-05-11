type NotFoundCopy = {
  title: string;
  subtitle: string;
  action: string;
};

type NotFoundScreenProps = {
  copy: NotFoundCopy;
  homeHref: string;
};

export function NotFoundScreen({ copy, homeHref }: NotFoundScreenProps) {
  return (
    <section className="error404-screen" role="alert" aria-live="polite">
      <div className="error404-content">
        <p className="error404-brand">SVOM</p>
        <div className="error404-number" aria-hidden="true">
          <span className="error404-number-text">404</span>
        </div>
        <h1 className="error404-title">{copy.title}</h1>
        <p className="error404-subtitle">{copy.subtitle}</p>
        <a className="error404-action" href={homeHref}>
          {copy.action}
        </a>
      </div>
    </section>
  );
}
