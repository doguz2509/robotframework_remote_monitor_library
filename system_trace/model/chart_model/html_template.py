
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
