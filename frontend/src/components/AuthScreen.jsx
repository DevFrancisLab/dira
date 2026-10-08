export function AuthScreen({ title, children, switchText, switchLabel, onSwitch }) {
  return (
    <main className="auth-screen">
      <section className="auth-panel">
        <p className="auth-mark">DIRA</p>
        <p className="auth-product">CAT Risk Intelligence</p>
        <h1>{title}</h1>
        {children}
        <p className="auth-switch">
          {switchText}{" "}
          <button type="button" onClick={onSwitch}>
            {switchLabel}
          </button>
        </p>
      </section>
    </main>
  );
}
