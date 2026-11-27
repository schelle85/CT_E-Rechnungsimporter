import { createElement } from "react";

export type NotificationBody = { content: string; contentType?: "HTML" | "Text" };

export function NotificationPreview({ body }: { body: NotificationBody }) {
  if (body.contentType !== "HTML") return createElement("div", { style: { whiteSpace: "pre-wrap" } }, body.content);
  const policy = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'";
  const document = '<!doctype html><meta http-equiv="Content-Security-Policy" content="' + policy
    + '"><meta name="referrer" content="no-referrer">' + body.content;
  return createElement("iframe", { title: "Inhalt der Testmail", sandbox: "", referrerPolicy: "no-referrer",
    srcDoc: document, style: { width: "100%", height: 440, border: 0 } });
}
