import AppKit
import PDFKit
import Foundation

guard CommandLine.arguments.count == 3 else {
    fputs("usage: render_pdf.swift input.pdf output_dir\n", stderr)
    exit(2)
}

let inputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outputURL = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
try FileManager.default.createDirectory(at: outputURL, withIntermediateDirectories: true)

guard let document = PDFDocument(url: inputURL) else {
    fputs("could not open PDF\n", stderr)
    exit(3)
}

let scale: CGFloat = 2.0
for index in 0..<document.pageCount {
    guard let page = document.page(at: index) else { continue }
    let box = page.bounds(for: .mediaBox)
    let pixelWidth = Int(box.width * scale)
    let pixelHeight = Int(box.height * scale)
    guard let rep = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: pixelWidth,
        pixelsHigh: pixelHeight,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: false,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ) else { continue }
    rep.size = NSSize(width: box.width, height: box.height)
    guard let context = NSGraphicsContext(bitmapImageRep: rep) else { continue }
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = context
    context.cgContext.setFillColor(NSColor.white.cgColor)
    context.cgContext.fill(CGRect(x: 0, y: 0, width: box.width, height: box.height))
    page.draw(with: .mediaBox, to: context.cgContext)
    NSGraphicsContext.restoreGraphicsState()
    if let data = rep.representation(using: .png, properties: [:]) {
        let name = String(format: "page-%02d.png", index + 1)
        try data.write(to: outputURL.appendingPathComponent(name))
    }
}
print("pages=\(document.pageCount)")
