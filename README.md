
< PROJECT ROOT >
   |
   |    
   |-- apps/
   |    |
   |    |-- api/
   |    |    |-- __init__.py
   |    |    |-- forms.py
   |    |    |-- routes.py
   |    |
   |    |-- authentication/                 # Handles auth routes (login and register)
   |    |    |-- __init__.py 
   |    |    |-- decorators.py 
   |    |    |-- forms.py                   # Define auth forms (login and register) 
   |    |    |-- models.py                  # Defines models  
   |    |    |-- oauth.py 
   |    |    |-- routes.py                  # Define authentication routes  
   |    |    |-- util.py                               
   |    |
   |    |-- home/                           # A simple app that serve HTML files
   |    |    |-- __init__.py
   |    |    |-- routes.py                  # Define app routes
   |    |
   |    |-- static/
   |    |    |-- <css, JS, images>          # CSS files, Javascripts files
   |    |
   |    |-- templates/                      # Templates used to render pages
   |    |    |-- accounts/                  # Authentication pages
   |    |    |    |-- login.html            # Login page
   |    |    |    |-- register.html         # Register page
   |    |    |  
   |    |    |-- home/                      # UI Kit Pages
   |    |    |    |-- accident-reports.html 
   |    |    |    |-- alerts.html 
   |    |    |    |-- billing.html 
   |    |    |    |-- data-visual.html 
   |    |    |    |-- emergency-services.html 
   |    |    |    |-- index.html            # Index page
   |    |    |    |-- page-403.html         # 404 page
   |    |    |    |-- page-404.html         # 403 page
   |    |    |    |-- page-500.html         # 500 page
   |    |    |    |-- profile.html 
   |    |    |    |-- settings.html 
   |    |    |    |-- sign-in.html 
   |    |    |    |-- sign-up.html 
   |    |    |    |-- surveillance.html 
   |    |    |    |-- video-record.html 
   |    |    |
   |    |    |-- includes/                  # HTML chunks and components
   |    |    |    |-- fixed-plugin.html
   |    |    |    |-- footer-fullscreen.html
   |    |    |    |-- footer.html           #APP footer
   |    |    |    |-- navigation-fullscreen.html
   |    |    |    |-- navigation.html       # Top menu component
   |    |    |    |-- sidebar.html          # Sidebar component
   |    |    |    |-- scripts.html          # Scripts common to all pages
   |    |    |
   |    |    |-- layouts/                   # Master pages
   |    |    |    |-- base-fullscreen.html  # Used by Authentication pages
   |    |    |    |-- base.html             # Used by common pages
   |    |    |
   |    |    
   |  config.py                             # Set up the app
   |    __init__.py                         # Initialize the app
   |
   |-- requirements.txt                     # App Dependencies
   |
   |-- .env                                 # Inject Configuration via Environment
   |-- run.py                               # Start the app - WSGI gateway
   |
   |-- ************************************************************************
```

