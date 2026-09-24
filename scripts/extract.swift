import Foundation
import Vision
import PDFKit
import AppKit

func recognize(_ image: CGImage) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "zh-Hant", "en-US"]
    request.usesLanguageCorrection = true
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    return (request.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

func extract(_ path: String, _ kind: String) throws -> [[String: Any]] {
    let url = URL(fileURLWithPath: path)
    if kind == "pdf" {
        guard let doc = PDFDocument(url: url) else { throw NSError(domain: "PDF 无法打开", code: 1) }
        guard doc.pageCount <= 300 else { throw NSError(domain: "PDF 超过 300 页处理上限", code: 2) }
        var result = [[String: Any]]()
        for index in 0..<doc.pageCount {
            guard let page = doc.page(at: index) else { continue }
            var text = page.string ?? ""
            if text.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 {
                let image = page.thumbnail(of: NSSize(width: 1600, height: 1600), for: .mediaBox)
                var rect = CGRect(origin: .zero, size: image.size)
                if let cg = image.cgImage(forProposedRect: &rect, context: nil, hints: nil) { text = try recognize(cg) }
            }
            result.append(["page": index + 1, "text": text])
        }
        return result
    }
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
          let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceThumbnailMaxPixelSize: 2400, kCGImageSourceCreateThumbnailWithTransform: true] as CFDictionary)
    else { throw NSError(domain: "图片无法读取", code: 3) }
    return [["page": 1, "text": try recognize(image)]]
}

do {
    guard CommandLine.arguments.count == 3 else { throw NSError(domain: "需要文件路径和类型", code: 4) }
    let pages = try extract(CommandLine.arguments[1], CommandLine.arguments[2])
    let data = try JSONSerialization.data(withJSONObject: pages, options: [.sortedKeys])
    FileHandle.standardOutput.write(data)
} catch {
    FileHandle.standardError.write(Data("本地提取失败：\(error.localizedDescription)\n".utf8))
    exit(1)
}
