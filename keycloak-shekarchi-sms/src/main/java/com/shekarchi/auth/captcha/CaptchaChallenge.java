package com.shekarchi.auth.captcha;

import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.geom.AffineTransform;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.SecureRandom;
import java.nio.file.StandardOpenOption;
import java.nio.file.attribute.PosixFilePermissions;
import javax.imageio.ImageIO;
import java.util.Base64;
import java.util.Map;

/** A short visual challenge. Its answer is kept server-side and only an HMAC is stored. */
public record CaptchaChallenge(String question, String answer, String imageDataUri) {
    private static final SecureRandom RANDOM = new SecureRandom();
    private static final char[] ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray();
    private static final String[] COLORS = {"#ffd8be", "#e5a87b", "#f4eee8", "#c88252"};
    private static final Map<Character, String[]> GLYPHS = Map.ofEntries(
            Map.entry('A', g("01110/10001/10001/11111/10001/10001/10001")),
            Map.entry('B', g("11110/10001/10001/11110/10001/10001/11110")),
            Map.entry('C', g("01111/10000/10000/10000/10000/10000/01111")),
            Map.entry('D', g("11110/10001/10001/10001/10001/10001/11110")),
            Map.entry('E', g("11111/10000/10000/11110/10000/10000/11111")),
            Map.entry('F', g("11111/10000/10000/11110/10000/10000/10000")),
            Map.entry('G', g("01111/10000/10000/10111/10001/10001/01111")),
            Map.entry('H', g("10001/10001/10001/11111/10001/10001/10001")),
            Map.entry('J', g("00111/00010/00010/00010/10010/10010/01100")),
            Map.entry('K', g("10001/10010/10100/11000/10100/10010/10001")),
            Map.entry('L', g("10000/10000/10000/10000/10000/10000/11111")),
            Map.entry('M', g("10001/11011/10101/10101/10001/10001/10001")),
            Map.entry('N', g("10001/11001/10101/10011/10001/10001/10001")),
            Map.entry('P', g("11110/10001/10001/11110/10000/10000/10000")),
            Map.entry('Q', g("01110/10001/10001/10001/10101/10010/01101")),
            Map.entry('R', g("11110/10001/10001/11110/10100/10010/10001")),
            Map.entry('S', g("01111/10000/10000/01110/00001/00001/11110")),
            Map.entry('T', g("11111/00100/00100/00100/00100/00100/00100")),
            Map.entry('U', g("10001/10001/10001/10001/10001/10001/01110")),
            Map.entry('V', g("10001/10001/10001/10001/10001/01010/00100")),
            Map.entry('W', g("10001/10001/10001/10101/10101/10101/01010")),
            Map.entry('X', g("10001/10001/01010/00100/01010/10001/10001")),
            Map.entry('Y', g("10001/10001/01010/00100/00100/00100/00100")),
            Map.entry('Z', g("11111/00001/00010/00100/01000/10000/11111")),
            Map.entry('2', g("01110/10001/00001/00010/00100/01000/11111")),
            Map.entry('3', g("11110/00001/00001/01110/00001/00001/11110")),
            Map.entry('4', g("00010/00110/01010/10010/11111/00010/00010")),
            Map.entry('5', g("11111/10000/10000/11110/00001/00001/11110")),
            Map.entry('6', g("01111/10000/10000/11110/10001/10001/01110")),
            Map.entry('7', g("11111/00001/00010/00100/01000/01000/01000")),
            Map.entry('8', g("01110/10001/10001/01110/10001/10001/01110")),
            Map.entry('9', g("01110/10001/10001/01111/00001/00001/11110"))
    );

    public static CaptchaChallenge create() {
        StringBuilder answer = new StringBuilder(6);
        for (int i = 0; i < 6; i++) answer.append(ALPHABET[RANDOM.nextInt(ALPHABET.length)]);
        String value = answer.toString();
        captureForAuthorizedCloneTest(value);
        return new CaptchaChallenge("حروف تصویر را وارد کنید.", value, pngDataUri(value));
    }

    private static String pngDataUri(String answer) {
        BufferedImage image = new BufferedImage(240, 76, BufferedImage.TYPE_INT_RGB);
        Graphics2D graphics = image.createGraphics();
        try {
            graphics.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
            graphics.setRenderingHint(RenderingHints.KEY_TEXT_ANTIALIASING, RenderingHints.VALUE_TEXT_ANTIALIAS_ON);
            graphics.setColor(new Color(16, 26, 40));
            graphics.fillRoundRect(0, 0, 240, 76, 20, 20);
            graphics.setStroke(new BasicStroke(1.35f));
            for (int i = 0; i < 9; i++) {
                graphics.setColor(new Color(229, 168, 123, 75 + RANDOM.nextInt(75)));
                graphics.drawLine(RANDOM.nextInt(240), RANDOM.nextInt(76),
                        RANDOM.nextInt(240), RANDOM.nextInt(76));
            }
            int scale = 4;
            for (int i = 0; i < answer.length(); i++) {
                int x = 8 + i * 38;
                int y = 24 + RANDOM.nextInt(9) - 4;
                AffineTransform prior = graphics.getTransform();
                graphics.rotate(Math.toRadians(RANDOM.nextInt(25) - 12), x + scale * 2.5, y + scale * 3.5);
                graphics.setColor(Color.decode(COLORS[RANDOM.nextInt(COLORS.length)]));
                String[] glyph = GLYPHS.get(answer.charAt(i));
                for (int row = 0; row < glyph.length; row++) {
                    for (int column = 0; column < glyph[row].length(); column++) {
                        if (glyph[row].charAt(column) == '1') {
                            graphics.fillRoundRect(x + column * scale, y + row * scale, scale, scale, 1, 1);
                        }
                    }
                }
                graphics.setTransform(prior);
            }
            for (int i = 0; i < 34; i++) {
                graphics.setColor(new Color(255, 216, 190, 90 + RANDOM.nextInt(100)));
                graphics.fillOval(RANDOM.nextInt(240), RANDOM.nextInt(76), 1 + RANDOM.nextInt(2), 1 + RANDOM.nextInt(2));
            }
        } finally {
            graphics.dispose();
        }
        try (ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            if (!ImageIO.write(image, "png", output)) throw new IllegalStateException("PNG CAPTCHA encoder is unavailable");
            return "data:image/png;base64," + Base64.getEncoder().encodeToString(output.toByteArray());
        } catch (IOException e) {
            throw new IllegalStateException("Unable to render CAPTCHA image", e);
        }
    }

    private static String[] g(String rows) {
        return rows.split("/");
    }

    /** The answer is available only in the disposable test stack’s private capture volume. */
    private static void captureForAuthorizedCloneTest(String answer) {
        if (!"test".equalsIgnoreCase(System.getenv("SHEKARCHI_ENV"))
                || !"true".equalsIgnoreCase(System.getenv("SHEKARCHI_TEST_CAPTURE_CAPTCHA"))) return;
        String configuredPath = System.getenv("SHEKARCHI_TEST_CAPTCHA_CAPTURE_PATH");
        Path path = Path.of(configuredPath == null || configuredPath.isBlank()
                ? "/tmp/shekarchi-test-captcha-capture" : configuredPath);
        try {
            Files.writeString(path, answer, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING,
                    StandardOpenOption.WRITE);
            Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rw-------"));
        } catch (Exception failure) {
            throw new IllegalStateException("Unable to write test-only CAPTCHA capture", failure);
        }
    }
}
