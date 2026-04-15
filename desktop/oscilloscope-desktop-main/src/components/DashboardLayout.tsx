import type { ReactNode } from "react";

type Props = {
  header: ReactNode;
  main: ReactNode;
  rail: ReactNode;
  footer: ReactNode;
};

export function DashboardLayout({ header, main, rail, footer }: Props) {
  return (
    <div className="scope-app">
      {header}
      <div className="scope-app__body">
        <main className="scope-app__main">{main}</main>
        {rail}
      </div>
      {footer}
    </div>
  );
}
