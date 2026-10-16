#import <AppKit/AppKit.h>
#import <PDFKit/PDFKit.h>

int main(int argc, const char * argv[]) {
    @autoreleasepool {
        if (argc != 3) {
            fprintf(stderr, "usage: render_pdf input.pdf output_dir\n");
            return 2;
        }
        NSString *input = [NSString stringWithUTF8String:argv[1]];
        NSString *output = [NSString stringWithUTF8String:argv[2]];
        [[NSFileManager defaultManager] createDirectoryAtPath:output withIntermediateDirectories:YES attributes:nil error:nil];
        PDFDocument *doc = [[PDFDocument alloc] initWithURL:[NSURL fileURLWithPath:input]];
        if (!doc) return 3;
        CGFloat scale = 2.0;
        for (NSInteger i = 0; i < doc.pageCount; i++) {
            PDFPage *page = [doc pageAtIndex:i];
            NSRect box = [page boundsForBox:kPDFDisplayBoxMediaBox];
            NSInteger width = (NSInteger)ceil(box.size.width * scale);
            NSInteger height = (NSInteger)ceil(box.size.height * scale);
            NSBitmapImageRep *rep = [[NSBitmapImageRep alloc]
                initWithBitmapDataPlanes:NULL pixelsWide:width pixelsHigh:height
                bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO
                colorSpaceName:NSDeviceRGBColorSpace bytesPerRow:0 bitsPerPixel:32];
            rep.size = box.size;
            NSGraphicsContext *ctx = [NSGraphicsContext graphicsContextWithBitmapImageRep:rep];
            [NSGraphicsContext saveGraphicsState];
            [NSGraphicsContext setCurrentContext:ctx];
            [[NSColor whiteColor] setFill];
            NSRectFill(NSMakeRect(0, 0, box.size.width, box.size.height));
            [page drawWithBox:kPDFDisplayBoxMediaBox toContext:ctx.CGContext];
            [NSGraphicsContext restoreGraphicsState];
            NSData *png = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
            NSString *name = [NSString stringWithFormat:@"page-%02ld.png", (long)(i + 1)];
            [png writeToFile:[output stringByAppendingPathComponent:name] atomically:YES];
        }
        printf("pages=%ld\n", (long)doc.pageCount);
    }
    return 0;
}
