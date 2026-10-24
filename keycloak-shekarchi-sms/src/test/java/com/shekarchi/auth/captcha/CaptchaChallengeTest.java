package com.shekarchi.auth.captcha;

import org.junit.jupiter.api.Test;

import javax.imageio.ImageIO;
import java.io.ByteArrayInputStream;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;

class CaptchaChallengeTest {
    @Test
    void rendersRasterImageWithoutEmbeddingTheAnswerAsText() throws Exception {
        CaptchaChallenge challenge = CaptchaChallenge.create();
        assertTrue(challenge.answer().matches("[A-Z2-9]{6}"));
        assertTrue(challenge.imageDataUri().startsWith("data:image/png;base64,"));
        assertFalse(challenge.imageDataUri().contains(challenge.answer()));

        byte[] png = Base64.getDecoder().decode(challenge.imageDataUri().substring("data:image/png;base64,".length()));
        var image = ImageIO.read(new ByteArrayInputStream(png));
        assertNotNull(image);
        assertEquals(240, image.getWidth());
        assertEquals(76, image.getHeight());
    }
}
