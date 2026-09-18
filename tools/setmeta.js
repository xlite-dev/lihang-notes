// Set /Info metadata on a PDF (mupdf):
//   mutool run setmeta.js in.pdf out.pdf Key=Value [Key=Value ...]
//
// Example:
//   mutool run setmeta.js draft.pdf final.pdf \
//       "Author=DefTruth" \
//       "Title=Microsoft Word - 李航《统计学习方法》笔记 --从原理到实现：基于R.docx"
//
// pdfunite and mutool merge drop /Info metadata, so run this AFTER merging.
// Values are UTF-8. Keys go into the PDF /Info dictionary (Title, Author,
// Subject, Keywords, Creator, Producer, CreationDate, ModDate, ...).

var files = [], kvs = [];
for (var i = 0; i < scriptArgs.length; i++) {
  var a = scriptArgs[i];
  if (/^[A-Za-z][A-Za-z0-9]*=/.test(a)) kvs.push(a);
  else files.push(a);
}
if (files.length < 2 || kvs.length === 0) {
  print("usage: mutool run setmeta.js in.pdf out.pdf Key=Value [Key=Value ...]");
  quit(1);
}
var src = files[files.length - 2], dst = files[files.length - 1];
var doc = new PDFDocument(src);
var info = doc.getTrailer().get("Info");
if (!info || info.isNull()) {
  info = doc.newDictionary();
  doc.getTrailer().put("Info", info);
}
for (var i = 0; i < kvs.length; i++) {
  var eq = kvs[i].indexOf("=");
  var key = kvs[i].substring(0, eq), val = kvs[i].substring(eq + 1);
  info.put(key, doc.newString(val));
  print("  " + key + " = " + val);
}
doc.save(dst);
print("metadata written: " + dst);
