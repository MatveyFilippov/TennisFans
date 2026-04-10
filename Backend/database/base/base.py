import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


ENGINE = create_engine(settings.LINK_TO_DATABASE, echo=False)
Session = scoped_session(sessionmaker(bind=ENGINE))
