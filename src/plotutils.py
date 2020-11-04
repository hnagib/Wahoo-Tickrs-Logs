from bokeh.io import show, output_notebook
from bokeh.models import ColumnDataSource, HoverTool, Legend
from bokeh.models.callbacks import CustomJS
from bokeh.plotting import figure
from bokeh.models import Range1d, Step
import itertools

    
def plotts(df_plot, 
            ys=None,
            units=None,
            hover_vars=None,
            hide_hovers=[None],
            x_axis_type='datetime',
            xvar='timestamp',
            styles=['-'],
            palette=['#154ba6', '#3f8dff', '#7ec4ff', '#e73360'],
            bar_width=[24*60*60*900],
            circle_size=7.5,
            title=None,
            plot_height=325,
            plot_width=450,
            alphas=[0.75],
            line_width=3,
            bar_line_color='white',
            ylabel=None,
            xlabel=None,
            x_range=None,
            y_range=None,
            legend_position='below',
            legend_location='top_left',
            legend_orientation='horizontal',
            ts_format='%a %b %d %Y',
            bounded_bar_label='bounded',
            show_plot=True,
            tools='',
            active_scroll=None,
            toolbar_location='above'
           ):
    
    if ys is None:
        ys=df_plot.columns

    if units is None:
        units=['']*len(ys)
    
    df_plot = df_plot.reset_index().copy()

    if x_axis_type == 'datetime':
        df_plot['ts_str'] = df_plot[xvar].dt.strftime(ts_format)
        df_plot['dt_str'] = df_plot[xvar].dt.strftime('%Y-%m-%d')

    cds = ColumnDataSource(data=df_plot)

    if y_range: 
        y_range = Range1d(y_range[0], y_range[1])        

    p = figure(
        x_axis_type=x_axis_type,
        plot_height=plot_height,
        plot_width=plot_width,
        x_range=x_range,
        y_range=y_range,
        title=title,
        tools=tools,
        active_scroll=active_scroll,
        active_drag=None,
        toolbar_location=toolbar_location
    )

    # Define a DataSource
    line_source = ColumnDataSource(data=dict(x=[df_plot[xvar][0]]))
    js = '''
    var geometry = cb_data['geometry'];
    console.log(geometry);
    var data = line_source.data;
    var x = data['x'];
    console.log(x);
    if (isFinite(geometry.x)) {
      for (i = 0; i < x.length; i++) {
        x[i] = geometry.x;
      }
      line_source.change.emit();
    }
    '''

    plot_dict = {}
    
#     if styles == ['/']:
#         plot_dict['stack'] = [p.vbar_stack(
#             ys,
#             x=xvar,
#             color=palette,
#             width=bar_width,
#             alpha=0.5,
#             source=cds
#         )]
    
    for y, color, style, width, alpha in zip(ys, itertools.cycle(palette),
                                      itertools.cycle(styles), itertools.cycle(bar_width),
                                      itertools.cycle(alphas)):
        plot_dict[y] = []
        
        if style == "--":
            plot_dict[y].append(p.line(
                x=xvar,
                y=y,
                line_dash="4 4",
                line_width=line_width,
                alpha=alpha,
                color=color, 
                source=cds
            ))    
            
        if ('-' in style) and (style != '--'):
            plot_dict[y].append(p.line(
                x=xvar,
                y=y,
                line_width=line_width,
                alpha=alpha,
                color=color, 
                source=cds
            ))
            
        if ("o" in style) or ("*" in style):
            plot_dict[y].append(p.circle(
                x=xvar,
                y=y,
                size=circle_size,
                color=color,
                alpha=alpha,
                source=cds
            ))
            
        if "|" in style:
            plot_dict[y].append(p.vbar(
                x=xvar,
                top=y,
                fill_color=color,
                line_color=bar_line_color,
                width=width,
                alpha=alpha,
                source=cds
            ))

        if "L" in style:
            glyph = Step(x=xvar, y=y, line_color=color, line_width=line_width, mode="after")
            plot_dict[y].append(p.add_glyph(cds, glyph))

    if "b" in style:
        plot_dict = {}
        plot_dict[bounded_bar_label] = []
        plot_dict[bounded_bar_label].append(p.vbar(
            x=xvar,
            top=ys[0],
            bottom=ys[1],
            fill_color=palette[0],
            line_color=bar_line_color,
            width=width,
            alpha=alpha,
            source=cds
        ))

    legend = Legend(items=[(var, plots) for var, plots in plot_dict.items()])
    p.add_layout(legend, legend_position)
    p.legend.click_policy = 'hide'
    p.legend.orientation = legend_orientation
    p.legend.location = legend_location
    p.legend.background_fill_alpha = 0.15
    p.legend.border_line_alpha = 0

    hovers = [(y, f'@{y} {unit}') for y, unit in zip(list(set(ys)-set(hide_hovers)), itertools.cycle(units))]

    if x_axis_type == 'datetime':
        hovers += [['Date', '@ts_str']]
    elif x_axis_type == 'linear':
        hovers += [[xvar, f'@{xvar}']]

    if hover_vars is not None:
        hovers += [[h, f'@{h}'] for h in hover_vars]
    
    p.add_tools(
        HoverTool(
            renderers=[v[0] for k,v in plot_dict.items()],
            tooltips=hovers, 
            point_policy='snap_to_data',
            line_policy='nearest'
        )
    )

    p.yaxis.axis_label = ylabel
    p.xaxis.axis_label = xlabel

    if show_plot:
        show(p)

    return p, cds
