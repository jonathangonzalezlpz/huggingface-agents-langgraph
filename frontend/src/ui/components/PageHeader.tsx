export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-1 max-w-prose text-fg-muted">{description}</p>
    </header>
  );
}
