package io.freemytv;

import java.util.ArrayList;
import java.util.List;

/** Reorders the shown keys without moving or discarding saved keys absent from the screen. */
final class VisibleOrder {
    private VisibleOrder() {}

    static List<String> replace(List<String> saved, List<String> ordered) {
        List<String> out = new ArrayList<>(saved);
        int next = 0;
        for (int slot = 0; slot < out.size() && next < ordered.size(); slot++) {
            if (ordered.contains(out.get(slot))) out.set(slot, ordered.get(next++));
        }
        // A button newly discovered since the saved snapshot has no slot yet.
        while (next < ordered.size()) out.add(ordered.get(next++));
        return out;
    }
}
