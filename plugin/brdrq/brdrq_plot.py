import sys

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QDoubleSpinBox,
    QLabel,
    QSizePolicy,
)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class MatplotlibWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.setMinimumSize(100, 100)

        # Original_data
        self.original_x = [0.0, 0.0]
        self.original_y = [0.0, 10.0]

        # DoubleSpinBox
        self.spinbox = QDoubleSpinBox()
        self.spinbox.setDecimals(1)
        self.spinbox.setSingleStep(0.1)
        self.spinbox.setRange(min(self.original_x), max(self.original_x))
        self.spinbox.setValue(5.0)

        # Matplotlib figure
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.ax = self.figure.add_subplot(111)

        # Layouts
        layout = QVBoxLayout()
        layout.addWidget(self.canvas)

        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Relevant Distance:"))
        control_layout.addWidget(self.spinbox)
        layout.addLayout(control_layout)

        self.setLayout(layout)

        # Combine signals
        self.spinbox.valueChanged.connect(self.update_line)

        # Mouse interaction
        self.dragging = False
        self.canvas.mpl_connect("button_press_event", self.on_click)
        self.canvas.mpl_connect("motion_notify_event", self.on_drag)
        self.canvas.mpl_connect("button_release_event", self.on_release)

        # Initialize plot
        self.reset_plot()

    def plot_data(self, x, y):
        self.ax.clear()
        self.ax.plot(x, y, 'b-')
        self.ax.set_xlim(min(x), max(x))
        self.ax.set_ylim(min(y), (max(y)*1.1)+0.1)
        self.ax.set_xlabel("Relevant distance (m)")
        self.ax.set_ylabel("Change (m²)")
        self.line = self.ax.axvline(x=self.spinbox.value(), color='red', linewidth=2)
        y_min, y_max = self.ax.get_ylim()
        y_mean = (y_max-y_min)/2
        self.arrow = self.ax.annotate("< >", xy=(self.spinbox.value(), y_mean), xytext=(self.spinbox.value(), y_mean),
                                         textcoords="data", ha="center", va="bottom", fontsize=10, color='red')
        self.figure.tight_layout()
        self.canvas.draw()

    def get_value(self):
        return self.spinbox.value()

    def spinbox_connect(self,function):
        self.spinbox.valueChanged.connect(function)

    def set_value(self, value):
        self.spinbox.setValue(value)

    def update_line(self, value):
        self.line.set_xdata([value])
        y_min, y_max = self.ax.get_ylim()
        y_mean = (y_max - y_min) / 2
        self.arrow.set_position((value, y_mean))
        self.canvas.draw()

    def reset_plot(self,max_x=1):
        if max_x is None or max_x<=0:
            max_x=1
        self.load_data([0,max_x], [0,0])

    def load_data(self, x, y):
        self.original_x = x
        self.original_y = y
        self.spinbox.setRange(min(x), max(x))
        self.plot_data(x, y)

    def on_click(self, event):
        if event.inaxes == self.ax and abs(event.xdata - self.line.get_xdata()[0]) < 0.2:
            self.dragging = True

    def on_drag(self, event):
        if self.dragging and event.inaxes == self.ax and event.xdata is not None:
            step = self.spinbox.singleStep()
            x = round(round(event.xdata / step) * step, 1)

            self.spinbox.setValue(x)
            self.update_line(x)

    def on_release(self, event):
        self.dragging = False

# Voor standalone testen
if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = MatplotlibWidget()
    widget.show()
    #widget.load_data([0,1,2],[0,1,4])

    # Voorbeeld van nieuwe data laden
    #widget.load_new_data([0.0, 2.5, 5.0, 7.5, 10.0], [0.0, 6.0, 3.0, 8.0, 2.0])

    sys.exit(app.exec_())
