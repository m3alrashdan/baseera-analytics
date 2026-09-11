declare module "jest-axe" {
  interface AxeViolation {
    id: string;
    impact?: string | null;
    description: string;
    help: string;
    helpUrl: string;
    nodes: unknown[];
  }

  interface AxeResults {
    violations: AxeViolation[];
  }

  export function axe(container: Element | string): Promise<AxeResults>;
}
