import test from "node:test";
import assert from "node:assert/strict";
import { recognitionText, attachmentNextStep, findingWarnings, mailCompletionHint } from "../src/processGuidance.ts";

const mixed={status:"unknown",reason:"ambiguous_mixed_document"};
const profile={status:"failed",reason:"unsupported_invoice_profile"};

test("only bounded PDF/XML warning codes have readable source-labelled guidance",()=>{
  assert.deepEqual(findingWarnings(mixed),[]);assert.deepEqual(findingWarnings(null),[]);
  const texts=findingWarnings({status:"recognized",reason:"hybrid_invoice_structure",warnings:["pdf_stream_missing_checksum","hybrid_xrechnung_metadata_version","private/path"]});
  assert.equal(texts.length,2);assert.match(texts[0],/PDF-Strukturprüfung.*Originaldatei bleibt unverändert/);
  assert.match(texts[1],/PDF-Metadaten.*keine vollständige Konformitätsprüfung/);
  assert.ok(texts.every(text=>!text.includes("private/path")));
});
test("unsupported profile identifies support gap without claiming supplier fault",()=>{
  assert.equal(recognitionText(profile),"Bei der letzten Prüfung wurde dieses Rechnungsprofil nicht unterstützt.");
  assert.doesNotMatch(recognitionText(profile),/Lieferantenfehler|Dateifehler/);
  assert.match(attachmentNextStep(profile,true,false),/Betreuung/);
  assert.equal(attachmentNextStep(profile,true,false),"Bitte die Betreuung informieren.");
});
test("ambiguous PDF guidance respects actual reader and correction gates",()=>{
  assert.match(recognitionText(mixed),/Bestellreferenz/);
  assert.match(attachmentNextStep(mixed,false,true),/Leserechte/);
  assert.match(attachmentNextStep(mixed,true,false),/gesperrt/);
  assert.match(attachmentNextStep(mixed,true,true),/nur bei eindeutiger Dokumentart/);
});
test("XML structure failure remains undecided until checked",()=>{
  const malformed={status:"failed",reason:"malformed_invoice"};
  assert.match(recognitionText(malformed),/Datei und Formatunterstützung/);
  assert.match(attachmentNextStep(malformed,true,false),/erst nach bestätigtem Dateifehler/);
});
test("completed Outlook flag is a separate explicit decision, never automatic reset",()=>{
  for(const canEdit of [false,true]){
    const text=mailCompletionHint("graph_existing_completed_flag",canEdit);
    assert.match(text,/beibehalten oder.*reaktiviert/);
    assert.match(text,/nicht automatisch zurück/);
    assert.match(text,canEdit?/vor.*Wiederholung/:/Leserechte/);
  }
  assert.equal(mailCompletionHint(null,true),null);
  assert.equal(mailCompletionHint("other",true),null);
});
