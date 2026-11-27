import { test } from "node:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import { NotificationPreview } from "../src/NotificationPreview.ts";

test("new HTML testmail is isolated with no sandbox permissions and restrictive resource policy", () => {
  const body={contentType:"HTML",content:'<h1>Test</h1><script>alert(1)</script><img src="https://remote.invalid/x">'};
  const node=NotificationPreview({body});
  assert.equal(node.type,"iframe");assert.equal(node.props.sandbox,"");
  assert.equal(node.props.referrerPolicy,"no-referrer");
  assert.match(node.props.srcDoc,/default-src 'none'/);assert.match(node.props.srcDoc,/form-action 'none'/);
  assert.ok(node.props.srcDoc.indexOf("Content-Security-Policy") < node.props.srcDoc.indexOf("<script>"));
  assert.equal(node.props.dangerouslySetInnerHTML,undefined);
  const html=renderToStaticMarkup(node);
  assert.ok(html.includes('sandbox=""'));assert.ok(!html.includes("<script>"));assert.ok(!html.includes("<img "));
});

test("historical explicit Text and missing contentType remain readable escaped text", () => {
  for(const contentType of ["Text",undefined]){
    const node=NotificationPreview({body:{contentType,content:'Zeile 1\n<img src=x> & Hinweis'}});
    assert.equal(node.type,"div");assert.equal(node.props.style.whiteSpace,"pre-wrap");
    const html=renderToStaticMarkup(node);
    assert.ok(html.includes("Zeile 1\n&lt;img"));assert.ok(!html.includes("<iframe"));
  }
});
