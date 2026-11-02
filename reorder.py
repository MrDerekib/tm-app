"""Drag and drop ordering for action lists, without triggering double-click actions."""
import tkinter as tk

from ui_theme import UI


class ListboxReorder:
    def __init__(self, widget, on_move, *, enabled=lambda: True, on_double_click=None,
                 on_feedback=None, drop_message='Orden actualizado'):
        self.widget = widget
        self.on_move = on_move
        self.enabled = enabled
        self.on_double_click = on_double_click
        self.on_feedback = on_feedback
        self.drop_message = drop_message
        self.source = None
        self.dragging = False
        self.cancelled = False
        self.previous_drag = False
        self.scroll_job = None
        self.ghost = None
        self.marker = tk.Frame(widget, background=widget.cget('selectbackground'), height=4)
        widget.bind('<ButtonPress-1>', self.press)
        widget.bind('<B1-Motion>', self.motion)
        widget.bind('<ButtonRelease-1>', self.release)
        widget.bind('<Motion>', self.hover)
        widget.bind('<Leave>', self.leave)
        widget.bind('<Escape>', self.cancel)
        widget.bind('<Destroy>', self.destroy, add='+')
        if on_double_click is not None:
            widget.bind('<Double-ButtonRelease-1>', self.double_release)

    def feedback(self, text):
        if self.on_feedback is not None:
            self.on_feedback(text)

    def contains(self, x, y):
        return 0 <= x < self.widget.winfo_width() and 0 <= y < self.widget.winfo_height()

    def hover(self, event):
        if not self.dragging and not self.cancelled:
            bounds = self.widget.bbox(self.widget.nearest(event.y)) if self.widget.size() else None
            ready = self.enabled() and self.contains(event.x, event.y) and bounds and bounds[1] <= event.y < bounds[1] + bounds[3]
            self.widget.configure(cursor='hand2' if ready else '')

    def leave(self, event):
        if not self.dragging:
            self.widget.configure(cursor='')

    def press(self, event):
        self.reset()
        if not self.enabled() or not self.widget.size():
            return
        index = self.widget.nearest(event.y)
        bounds = self.widget.bbox(index)
        if bounds and bounds[1] <= event.y < bounds[1] + bounds[3]:
            self.source = index
            self.origin = (event.x, event.y)
            self.items = self.widget.get(0, 'end')

    def motion(self, event):
        if self.cancelled:
            return 'break'
        if self.source is None:
            return
        if not self.enabled():
            self.cancel()
            return 'break'
        if not self.dragging and max(abs(event.x - self.origin[0]), abs(event.y - self.origin[1])) < 5:
            return 'break'
        self.dragging = True
        self.pointer = (event.x, event.y)
        self.show_target()
        if self.scroll_job is None:
            self.scroll_job = self.widget.after(100, self.scroll)
        return 'break'

    def show_target(self):
        x, y = self.pointer
        valid = self.contains(x, y)
        self.widget.configure(cursor='sb_v_double_arrow' if valid else 'no')
        if not valid:
            self.marker.place_forget()
            self.feedback('Fuera de la lista · Suelta para cancelar')
            self.show_ghost('Suelta para cancelar', valid=False)
            return
        target = self.widget.nearest(y)
        bounds = self.widget.bbox(target)
        if bounds and target != self.source:
            marker_y = bounds[1] if target < self.source else bounds[1] + bounds[3] - 4
            self.marker.place(x=0, y=marker_y, relwidth=1, height=4)
            self.marker.lift()
        else:
            self.marker.place_forget()
        destination = f'Posición {target + 1} de {len(self.items)}'
        self.feedback(f'{destination} · Suelta para colocar · Esc cancela')
        self.show_ghost(destination)

    def show_ghost(self, destination, *, valid=True):
        # A placed label floats over the owner without stealing keyboard focus
        # or changing list geometry; coordinates work on any monitor.
        owner = self.widget.winfo_toplevel()
        if self.ghost is None:
            self.ghost = tk.Label(owner, font=('Segoe UI', 10), justify='left', anchor='w',
                                  fg=UI['surface'], padx=10, pady=7, relief='solid', borderwidth=1,
                                  wraplength=280, takefocus=False)
        self.ghost.configure(text=f'{self.items[self.source]}\n{destination}',
                             bg=UI['accent'] if valid else UI['muted'],
                             cursor='sb_v_double_arrow' if valid else 'no')
        owner.update_idletasks()
        x = self.widget.winfo_rootx() - owner.winfo_rootx() + self.pointer[0] + 16
        y = self.widget.winfo_rooty() - owner.winfo_rooty() + self.pointer[1] + 18
        x = max(4, min(x, owner.winfo_width() - self.ghost.winfo_reqwidth() - 4))
        y = max(4, min(y, owner.winfo_height() - self.ghost.winfo_reqheight() - 4))
        self.ghost.place(x=x, y=y)
        self.ghost.lift()

    def scroll(self):
        self.scroll_job = None
        if not self.dragging:
            return
        if not self.enabled():
            self.cancel()
            return
        x, y = self.pointer
        if 0 <= x < self.widget.winfo_width():
            direction = -1 if y < 18 else 1 if y > self.widget.winfo_height() - 18 else 0
            if direction:
                self.widget.yview_scroll(direction, 'units')
        self.show_target()
        self.scroll_job = self.widget.after(100, self.scroll)

    def release(self, event):
        cancelled = self.cancelled
        dragged, source = self.dragging or cancelled, self.source
        items = self.items if source is not None else ()
        self.reset()
        self.previous_drag = dragged
        self.hover(event)
        if not dragged:
            return
        if cancelled:
            return 'break'
        if (self.enabled() and 0 <= event.x < self.widget.winfo_width()
                and 0 <= event.y < self.widget.winfo_height()
                and items == self.widget.get(0, 'end')):
            target = self.widget.nearest(event.y)
            if target != source and self.on_move(source, target):
                item = self.widget.get(source)
                self.widget.delete(source)
                self.widget.insert(target, item)
                self.widget.selection_clear(0, 'end')
                self.widget.selection_set(target)
                self.widget.activate(target)
                self.widget.see(target)
                self.widget.event_generate('<<ListboxSelect>>')
                self.feedback(f'{self.drop_message} · Posición {target + 1} de {len(items)}')
            elif target == source:
                self.feedback('Orden sin cambios')
            else:
                self.feedback('No se pudo cambiar el orden')
        else:
            self.feedback('Reordenación cancelada')
        return 'break'

    def double_release(self, event):
        suppress = self.dragging or self.cancelled or self.previous_drag
        self.release(event)
        if not suppress:
            self.on_double_click(event)
        return 'break'

    def cancel(self, event=None):
        if self.source is None and not self.dragging:
            return
        self.reset()
        self.cancelled = True
        self.previous_drag = True
        self.feedback('Reordenación cancelada')
        return 'break'

    def remove_ghost(self):
        if self.ghost is not None:
            if self.ghost.winfo_exists():
                self.ghost.destroy()
            self.ghost = None

    def reset(self):
        if self.scroll_job is not None:
            self.widget.after_cancel(self.scroll_job)
            self.scroll_job = None
        self.marker.place_forget()
        self.remove_ghost()
        self.widget.configure(cursor='')
        self.source = None
        self.dragging = False
        self.cancelled = False

    def destroy(self, event):
        if event.widget is self.widget:
            if self.scroll_job is not None:
                self.widget.after_cancel(self.scroll_job)
                self.scroll_job = None
            self.remove_ghost()
