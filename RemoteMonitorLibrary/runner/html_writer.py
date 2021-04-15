import os
from typing import List, Tuple

HTML = """
<!DOCTYPE html>
<html>
    <head>
        <style>
            * {{
              box-sizing: border-box;
            }}
            
            .column {{
              float: left;
              width: 33.33%;
              padding: 5px;
            }}
            
            /* Clearfix (clear floats) */
            .row::after {{
              content: "";
              clear: both;
              display: table;
            }}
            
            @media screen and (max-width: 500px) {{
              .column {{
                width: 100%;
              }}
            }}
    </style>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <title>{title}</title>
</head>
    <body>
        <h1>{title}</h1><br>
        <div class="row">
          {body}
        </div>
    </body>
</html>
"""

HTML_IMAGE_REF = """
            <div class="column">
                <h3>{picture_title}</h3>
                <img src="{relative_path}" style="width:100%">
            </div>
"""


def create_html(report_abs_path, report_rel_path, file_name: str,
                body_data: List[Tuple[str, str]]) -> str:
    body = ''
    html_file_name = "{}.html".format(file_name) if not file_name.endswith('.html') else file_name
    html_full_path = os.path.normpath(os.path.join(report_abs_path, report_rel_path, html_file_name))
    html_link_path = '/'.join([report_rel_path, html_file_name])

    for file_path, picture_name in body_data:
        body += HTML_IMAGE_REF.format(relative_path=file_path, picture_title=picture_name)

    with open(html_full_path, 'w') as sw:
        sw.write(HTML.format(title=file_name, body=body))
    return html_link_path
