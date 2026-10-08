export async function loadPortfolio() {
  const response = await fetch("/api/portfolio/");
  if (!response.ok) {
    throw new Error("The portfolio API did not respond.");
  }
  return response.json();
}
