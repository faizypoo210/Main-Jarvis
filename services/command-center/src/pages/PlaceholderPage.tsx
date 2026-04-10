export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-20 text-center">
      <h2 className="font-display text-xl font-semibold text-[var(--text-primary)]">{title}</h2>
      <p className="max-w-sm text-sm text-[var(--text-secondary)]">This surface is wired next — mission control stays calm.</p>
    </div>
  );
}
