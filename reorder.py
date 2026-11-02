"""Drag and drop ordering for action lists, without triggering double-click actions."""
import tkinter as tk


class ListboxReorder:
    def __init__(self, widget, on_move, *, enabled=lambda: True, on_double_click=None):
        self.widget = widget
        self.on_move = on_move
        self.enabled = enabled
        self.on_double_click = on_double_click
        self.source = None
        self.dragging = False
        self.previous_drag = False
        self.scroll_job = None
        self.marker = tk.Frame(widget, background=widget.cget('selectbackground'), height=2)
        widget.bind('<ButtonPress-1>', self.press)
        widget.bind('<B1-Motion>', self.motion)
        widget.bind('<ButtonRelease-1>', self.release)
        widget.bind('<Destroy>', self.destroy, add='+')
        if on_double_click is not None:
            widget.bind('<Double-ButtonRelease-1>', self.double_release)

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
        if self.source is None:
            return
        if not self.enabled():
            self.reset()
            return 'break'
        if not self.dragging and max(abs(event.x - self.origin[0]), abs(event.y - self.origin[1])) < 5:
            return 'break'
        self.dragging = True
        self.pointer = (event.x, event.y)
        self.widget.configure(cursor='fleur')
        self.show_target()
        if self.scroll_job is None:
            self.scroll_job = self.widget.after(100, self.scroll)
        return 'break'

    def show_target(self):
        x, y = self.pointer
        if not 0 <= x < self.widget.winfo_width():
            self.marker.place_forget()
            return
        target = self.widget.nearest(y)
        bounds = self.widget.bbox(target)
        if bounds and target != self.source:
            marker_y = bounds[1] if target < self.source else bounds[1] + bounds[3] - 2
            self.marker.place(x=0, y=marker_y, relwidth=1, height=2)
        else:
            self.marker.place_forget()

    def scroll(self):
        self.scroll_job = None
        if not self.dragging or not self.enabled():
            self.reset()
            return
        x, y = self.pointer
        if 0 <= x < self.widget.winfo_width():
            direction = -1 if y < 18 else 1 if y > self.widget.winfo_height() - 18 else 0
            if direction:
                self.widget.yview_scroll(direction, 'units')
                self.show_target()
        self.scroll_job = self.widget.after(100, self.scroll)

    def release(self, event):
        dragged, source = self.dragging, self.source
        items = self.items if source is not None else ()
        self.reset()
        self.previous_drag = dragged
        if not dragged:
            return
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
        return 'break'

    def double_release(self, event):
        suppress = self.dragging or self.previous_drag
        self.release(event)
        if not suppress:
            self.on_double_click(event)
        return 'break'

    def reset(self):
        if self.scroll_job is not None:
            self.widget.after_cancel(self.scroll_job)
            self.scroll_job = None
        self.marker.place_forget()
        self.widget.configure(cursor='')
        self.source = None
        self.dragging = False

    def destroy(self, event):
        if event.widget is self.widget and self.scroll_job is not None:
            self.widget.after_cancel(self.scroll_job)
            self.scroll_job = None
